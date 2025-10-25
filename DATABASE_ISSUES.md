# Database Issues Report - llm_cost Project

Generated using Supabase Advisors (Security + Performance)

---

## 🔴 CRITICAL SECURITY ISSUES (5 Errors)

### Issue: Row Level Security (RLS) Not Enabled

**Severity**: ERROR  
**Category**: SECURITY  
**Impact**: All tables are publicly accessible without authentication

#### Affected Tables:

1. **`public.providers`**
   - Status: RLS DISABLED ❌
   - Risk: Anyone can read/write provider data
   - [Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public)

2. **`public.models_catalog`**
   - Status: RLS DISABLED ❌
   - Risk: Anyone can read/write model data
   - [Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public)

3. **`public.model_providers`**
   - Status: RLS DISABLED ❌
   - Risk: Anyone can read/write model-provider relationships
   - [Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public)

4. **`public.model_pricing_daily`**
   - Status: RLS DISABLED ❌
   - Risk: Anyone can read/write pricing data
   - [Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public)

5. **`public.byok_verifications`**
   - Status: RLS DISABLED ❌
   - Risk: Anyone can read/write verification data
   - [Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public)

### Fix: Enable RLS on All Tables

```sql
-- Enable RLS on all tables
ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.models_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_pricing_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.byok_verifications ENABLE ROW LEVEL SECURITY;

-- Create policy to allow service role full access
-- (Your Python app uses service role key)

CREATE POLICY "Allow service role full access to providers"
ON public.providers
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow service role full access to models_catalog"
ON public.models_catalog
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow service role full access to model_providers"
ON public.model_providers
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow service role full access to model_pricing_daily"
ON public.model_pricing_daily
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow service role full access to byok_verifications"
ON public.byok_verifications
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Optional: Allow public read-only access to pricing data
CREATE POLICY "Allow public read access to providers"
ON public.providers
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY "Allow public read access to models_catalog"
ON public.models_catalog
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY "Allow public read access to model_pricing_daily"
ON public.model_pricing_daily
FOR SELECT
TO anon, authenticated
USING (true);
```

---

## ⚠️ SECURITY WARNINGS (1 Warning)

### Issue: Function Search Path Mutable

**Severity**: WARNING  
**Category**: SECURITY  
**Function**: `public.update_updated_at_column`

**Problem**: The function has a role-mutable search_path, which can be exploited for SQL injection.

**Fix**:

```sql
-- Drop and recreate function with secure search_path
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public  -- FIX: Set explicit search_path
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Recreate triggers
CREATE TRIGGER update_providers_updated_at
    BEFORE UPDATE ON public.providers
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_models_catalog_updated_at
    BEFORE UPDATE ON public.models_catalog
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
```

[Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable)

---

## 📊 PERFORMANCE ISSUES (4 Info)

### 1. Unindexed Foreign Keys (2 Issues)

Foreign keys without indexes cause slow JOIN queries.

#### A. `byok_verifications.provider_id`

**Foreign Key**: `byok_verifications_provider_id_fkey`  
**Impact**: Slow queries when joining with providers table

**Fix**:
```sql
CREATE INDEX idx_byok_verifications_provider_id 
ON public.byok_verifications(provider_id);
```

#### B. `model_pricing_daily.provider_id`

**Foreign Key**: `model_pricing_daily_provider_id_fkey`  
**Impact**: Slow queries when joining with providers table

**Fix**:
```sql
CREATE INDEX idx_model_pricing_daily_provider_id 
ON public.model_pricing_daily(provider_id);
```

[Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys)

### 2. Unused Indexes (2 Issues)

Indexes that are never used waste storage and slow down writes.

#### A. `idx_models_canonical` on `models_catalog`

**Status**: Never used  
**Action**: Consider removing if not needed

```sql
-- Option 1: Drop if truly unused
DROP INDEX IF EXISTS public.idx_models_canonical;

-- Option 2: Keep if you plan to query by canonical_slug
-- (Currently your queries use or_model_slug, not canonical_slug)
```

#### B. `idx_pricing_snapshot_date` on `model_pricing_daily`

**Status**: Never used  
**Action**: Consider removing or verify if queries use it

```sql
-- Check if you query by snapshot_date alone
-- If not, consider dropping:
DROP INDEX IF EXISTS public.idx_pricing_snapshot_date;

-- If you do need date-based queries, keep it
```

[Fix Documentation](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index)

---

## 🔧 RECOMMENDED FIXES (Priority Order)

### Priority 1: CRITICAL SECURITY - Enable RLS (MUST DO)

```sql
-- Run this migration ASAP
-- File: migrations/001_enable_rls.sql

-- Enable RLS
ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.models_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_pricing_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.byok_verifications ENABLE ROW LEVEL SECURITY;

-- Service role policies (for your Python app)
CREATE POLICY "service_role_all_providers" ON public.providers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_models" ON public.models_catalog FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_model_providers" ON public.model_providers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_pricing" ON public.model_pricing_daily FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_byok" ON public.byok_verifications FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Public read-only policies (optional, for API access)
CREATE POLICY "public_read_providers" ON public.providers FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "public_read_models" ON public.models_catalog FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "public_read_pricing" ON public.model_pricing_daily FOR SELECT TO anon, authenticated USING (true);
```

### Priority 2: SECURITY WARNING - Fix Function Search Path

```sql
-- File: migrations/002_fix_function_security.sql

DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Recreate triggers
CREATE TRIGGER update_providers_updated_at BEFORE UPDATE ON public.providers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_models_catalog_updated_at BEFORE UPDATE ON public.models_catalog FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
```

### Priority 3: PERFORMANCE - Add Missing Indexes

```sql
-- File: migrations/003_add_performance_indexes.sql

-- Foreign key indexes for better JOIN performance
CREATE INDEX idx_byok_verifications_provider_id ON public.byok_verifications(provider_id);
CREATE INDEX idx_model_pricing_daily_provider_id ON public.model_pricing_daily(provider_id);

-- Additional useful indexes for common queries
CREATE INDEX idx_model_pricing_daily_model_provider ON public.model_pricing_daily(model_id, provider_id);
CREATE INDEX idx_model_pricing_daily_snapshot_model ON public.model_pricing_daily(snapshot_date, model_id);
```

### Priority 4: CLEANUP - Remove Unused Indexes (Optional)

```sql
-- File: migrations/004_cleanup_unused_indexes.sql

-- Only drop if you confirm these are truly unused
DROP INDEX IF EXISTS public.idx_models_canonical;
DROP INDEX IF EXISTS public.idx_pricing_snapshot_date;
```

---

## 📋 Summary

| Category | Count | Severity |
|----------|-------|----------|
| **Security Errors** | 5 | 🔴 CRITICAL |
| **Security Warnings** | 1 | ⚠️ WARNING |
| **Performance Info** | 4 | ℹ️ INFO |

### Immediate Actions Required:

1. ✅ **Enable RLS on all 5 tables** (blocks unauthorized access)
2. ✅ **Fix function search_path** (prevents SQL injection)
3. ✅ **Add foreign key indexes** (improves query performance)
4. 🔍 **Review unused indexes** (cleanup if confirmed unused)

### Impact if Not Fixed:

- **Security**: Database is publicly writable via PostgREST API
- **Performance**: Slow queries on large datasets (especially JOINs)
- **Compliance**: May violate data security requirements

---

## 🚀 Quick Fix Script

Run this in your Supabase SQL Editor:

```sql
-- ============================================
-- CRITICAL FIX: Enable RLS + Policies
-- ============================================

BEGIN;

-- Enable RLS
ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.models_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_pricing_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.byok_verifications ENABLE ROW LEVEL SECURITY;

-- Service role full access
CREATE POLICY "svc_all_providers" ON public.providers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "svc_all_models" ON public.models_catalog FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "svc_all_model_providers" ON public.model_providers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "svc_all_pricing" ON public.model_pricing_daily FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "svc_all_byok" ON public.byok_verifications FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Public read access
CREATE POLICY "pub_read_providers" ON public.providers FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "pub_read_models" ON public.models_catalog FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "pub_read_pricing" ON public.model_pricing_daily FOR SELECT TO anon, authenticated USING (true);

-- Fix function security
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER update_providers_updated_at BEFORE UPDATE ON public.providers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER update_models_catalog_updated_at BEFORE UPDATE ON public.models_catalog FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Add performance indexes
CREATE INDEX idx_byok_verifications_provider_id ON public.byok_verifications(provider_id);
CREATE INDEX idx_model_pricing_daily_provider_id ON public.model_pricing_daily(provider_id);
CREATE INDEX idx_model_pricing_daily_model_provider ON public.model_pricing_daily(model_id, provider_id);

COMMIT;
```

**Test after running**: `python -m app.main --once` should still work (uses service role key).

---

## 📚 References

- [Supabase RLS Documentation](https://supabase.com/docs/guides/auth/row-level-security)
- [Database Linter Guide](https://supabase.com/docs/guides/database/database-linter)
- [PostgreSQL Security](https://supabase.com/docs/guides/database/postgres/configuration)
