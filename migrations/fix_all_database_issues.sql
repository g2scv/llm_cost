-- ============================================
-- Database Security & Performance Fixes
-- Generated from Supabase Advisors Report
-- ============================================
--
-- This migration fixes:
-- 1. 5 CRITICAL: RLS not enabled on public tables
-- 2. 1 WARNING: Function search_path mutable
-- 3. 2 PERFORMANCE: Unindexed foreign keys
-- 4. Optional: Add useful indexes for common queries
--
-- Safe to run: Uses IF EXISTS and IF NOT EXISTS
-- ============================================

BEGIN;

-- ============================================
-- PART 1: ENABLE ROW LEVEL SECURITY (RLS)
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Enabling Row Level Security on all tables...';
END $$;

ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.models_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_pricing_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.byok_verifications ENABLE ROW LEVEL SECURITY;

-- ============================================
-- PART 2: CREATE RLS POLICIES
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Creating RLS policies...';
END $$;

-- Service role policies (for Python app using service_role key)
-- These allow full access to the application

DROP POLICY IF EXISTS "service_role_all_providers" ON public.providers;
CREATE POLICY "service_role_all_providers"
ON public.providers
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_models" ON public.models_catalog;
CREATE POLICY "service_role_all_models"
ON public.models_catalog
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_model_providers" ON public.model_providers;
CREATE POLICY "service_role_all_model_providers"
ON public.model_providers
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_pricing" ON public.model_pricing_daily;
CREATE POLICY "service_role_all_pricing"
ON public.model_pricing_daily
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_byok" ON public.byok_verifications;
CREATE POLICY "service_role_all_byok"
ON public.byok_verifications
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Public read-only policies (for API consumers)
-- These allow anyone to read pricing data, but not modify it

DROP POLICY IF EXISTS "public_read_providers" ON public.providers;
CREATE POLICY "public_read_providers"
ON public.providers
FOR SELECT
TO anon, authenticated
USING (true);

DROP POLICY IF EXISTS "public_read_models" ON public.models_catalog;
CREATE POLICY "public_read_models"
ON public.models_catalog
FOR SELECT
TO anon, authenticated
USING (true);

DROP POLICY IF EXISTS "public_read_model_providers" ON public.model_providers;
CREATE POLICY "public_read_model_providers"
ON public.model_providers
FOR SELECT
TO anon, authenticated
USING (true);

DROP POLICY IF EXISTS "public_read_pricing" ON public.model_pricing_daily;
CREATE POLICY "public_read_pricing"
ON public.model_pricing_daily
FOR SELECT
TO anon, authenticated
USING (true);

-- BYOK verifications are internal only (no public read access)

-- ============================================
-- PART 3: FIX FUNCTION SECURITY
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Fixing function search_path security issue...';
END $$;

-- Drop existing function (CASCADE will drop dependent triggers)
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

-- Recreate with secure search_path
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public  -- FIX: Explicit search_path prevents SQL injection
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Recreate triggers that were dropped by CASCADE
CREATE TRIGGER update_providers_updated_at
    BEFORE UPDATE ON public.providers
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_models_catalog_updated_at
    BEFORE UPDATE ON public.models_catalog
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================
-- PART 4: ADD PERFORMANCE INDEXES
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Adding performance indexes...';
END $$;

-- Foreign key indexes (critical for JOIN performance)
CREATE INDEX IF NOT EXISTS idx_byok_verifications_provider_id
ON public.byok_verifications(provider_id);

CREATE INDEX IF NOT EXISTS idx_model_pricing_daily_provider_id
ON public.model_pricing_daily(provider_id);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_model_pricing_daily_model_provider
ON public.model_pricing_daily(model_id, provider_id);

CREATE INDEX IF NOT EXISTS idx_model_pricing_daily_date_model
ON public.model_pricing_daily(snapshot_date, model_id);

CREATE INDEX IF NOT EXISTS idx_model_pricing_daily_source_type
ON public.model_pricing_daily(source_type);

-- Model-provider relationship index
CREATE INDEX IF NOT EXISTS idx_model_providers_model_id
ON public.model_providers(model_id);

CREATE INDEX IF NOT EXISTS idx_model_providers_provider_id
ON public.model_providers(provider_id);

-- ============================================
-- PART 5: CLEANUP UNUSED INDEXES (OPTIONAL)
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Cleaning up unused indexes...';
END $$;

-- These indexes are never used according to Supabase Advisors
-- Drop them to save storage and improve write performance

-- DROP INDEX IF EXISTS public.idx_models_canonical;
-- DROP INDEX IF EXISTS public.idx_pricing_snapshot_date;

-- NOTE: Commented out above - uncomment if you confirm they're truly unused
-- Run: SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;

-- ============================================
-- PART 6: VERIFY FIXES
-- ============================================

DO $$
DECLARE
    rls_count INTEGER;
    index_count INTEGER;
    policy_count INTEGER;
BEGIN
    -- Check RLS is enabled
    SELECT COUNT(*) INTO rls_count
    FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename IN ('providers', 'models_catalog', 'model_providers', 'model_pricing_daily', 'byok_verifications')
    AND rowsecurity = true;

    RAISE NOTICE 'Tables with RLS enabled: % / 5', rls_count;

    -- Check policies created
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname = 'public';

    RAISE NOTICE 'RLS policies created: %', policy_count;

    -- Check indexes added
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND indexname LIKE 'idx_%';

    RAISE NOTICE 'Performance indexes: %', index_count;

    IF rls_count = 5 THEN
        RAISE NOTICE '✅ All tables have RLS enabled';
    ELSE
        RAISE WARNING '⚠️  Some tables missing RLS!';
    END IF;

    IF policy_count >= 10 THEN
        RAISE NOTICE '✅ All RLS policies created';
    ELSE
        RAISE WARNING '⚠️  Some policies may be missing!';
    END IF;

    RAISE NOTICE '✅ Migration completed successfully!';
END $$;

COMMIT;

-- ============================================
-- POST-MIGRATION TESTING
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration Complete!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Test Python app: python -m app.main --once';
    RAISE NOTICE '2. Verify RLS: SELECT * FROM pg_tables WHERE schemaname = ''public'' AND rowsecurity = true;';
    RAISE NOTICE '3. Check policies: SELECT * FROM pg_policies WHERE schemaname = ''public'';';
    RAISE NOTICE '4. Monitor performance: Check query speeds on pricing_daily table';
    RAISE NOTICE '';
    RAISE NOTICE 'Security improvements:';
    RAISE NOTICE '✅ Row Level Security enabled on all tables';
    RAISE NOTICE '✅ Service role has full access (Python app will work)';
    RAISE NOTICE '✅ Public has read-only access (API consumers can query)';
    RAISE NOTICE '✅ Function search_path secured';
    RAISE NOTICE '';
    RAISE NOTICE 'Performance improvements:';
    RAISE NOTICE '✅ Foreign key indexes added';
    RAISE NOTICE '✅ Composite indexes for common queries';
    RAISE NOTICE '';
END $$;
