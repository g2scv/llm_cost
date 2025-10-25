-- Migration: Initial schema for OpenRouter LLM pricing tracker
-- Created: 2025-10-25
-- Description: Creates tables for providers, models, pricing snapshots, and BYOK verification

-- Providers known in OpenRouter universe
CREATE TABLE IF NOT EXISTS providers (
  provider_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,         -- e.g., 'openai', 'anthropic', 'deepinfra'
  display_name TEXT NOT NULL,
  homepage_url TEXT,
  pricing_url TEXT,                  -- official pricing page if exists
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_providers_slug ON providers(slug);

-- Catalog of models (de-duplicated by OpenRouter model id/slug)
CREATE TABLE IF NOT EXISTS models_catalog (
  model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  or_model_slug TEXT UNIQUE NOT NULL, -- e.g., 'anthropic/claude-3.5-sonnet'
  canonical_slug TEXT,                -- from Models API
  display_name TEXT,
  context_length INT,                 -- from Models API
  architecture JSONB,                 -- 'architecture' object from Models API
  supported_parameters JSONB,         -- array from Models API
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_models_or_slug ON models_catalog(or_model_slug);
CREATE INDEX IF NOT EXISTS idx_models_canonical ON models_catalog(canonical_slug);

-- Link models to providers (when we can attribute a provider variant)
CREATE TABLE IF NOT EXISTS model_providers (
  model_provider_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES models_catalog(model_id) ON DELETE CASCADE,
  provider_id UUID REFERENCES providers(provider_id) ON DELETE CASCADE,
  is_top_provider BOOLEAN DEFAULT FALSE,  -- aligns with Models API 'top_provider'
  provider_metadata JSONB,                -- context_length, max_completion_tokens, etc.
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(model_id, provider_id)
);

-- Create indexes for faster joins
CREATE INDEX IF NOT EXISTS idx_model_providers_model ON model_providers(model_id);
CREATE INDEX IF NOT EXISTS idx_model_providers_provider ON model_providers(provider_id);

-- Daily pricing snapshots (immutable history, 1 row per model/provider/day/source)
CREATE TABLE IF NOT EXISTS model_pricing_daily (
  pricing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES models_catalog(model_id) ON DELETE CASCADE,
  provider_id UUID REFERENCES providers(provider_id) ON DELETE SET NULL,
  snapshot_date DATE NOT NULL,           -- e.g., 2025-10-25
  source_type TEXT NOT NULL,             -- 'openrouter_api' | 'provider_site' | 'web_fallback'
  source_url TEXT,                       -- cite where we got the price
  prompt_usd_per_million NUMERIC(18,8),  -- normalized
  completion_usd_per_million NUMERIC(18,8),
  request_usd NUMERIC(18,8),             -- fixed per-request if applicable
  image_usd NUMERIC(18,8),
  web_search_usd NUMERIC(18,8),
  internal_reasoning_usd_per_million NUMERIC(18,8),
  input_cache_read_usd_per_million NUMERIC(18,8),
  input_cache_write_usd_per_million NUMERIC(18,8),
  currency TEXT DEFAULT 'USD',
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT,
  UNIQUE(model_id, provider_id, snapshot_date, source_type)
);

-- Create indexes for historical queries
CREATE INDEX IF NOT EXISTS idx_pricing_model ON model_pricing_daily(model_id);
CREATE INDEX IF NOT EXISTS idx_pricing_snapshot_date ON model_pricing_daily(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_pricing_source_type ON model_pricing_daily(source_type);

-- Optional: simple audit of BYOK spot-checks
CREATE TABLE IF NOT EXISTS byok_verifications (
  verify_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES models_catalog(model_id) ON DELETE CASCADE,
  provider_id UUID REFERENCES providers(provider_id) ON DELETE SET NULL,
  run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  prompt_tokens INT,
  completion_tokens INT,
  openrouter_cost_usd NUMERIC(18,8),     -- 'cost' from usage
  upstream_cost_usd NUMERIC(18,8),       -- 'cost_details.upstream_inference_cost'
  response_ms INT,
  ok BOOLEAN NOT NULL DEFAULT TRUE,
  raw_usage JSONB
);

-- Create index for verification queries
CREATE INDEX IF NOT EXISTS idx_byok_model ON byok_verifications(model_id);
CREATE INDEX IF NOT EXISTS idx_byok_run_at ON byok_verifications(run_at);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add updated_at triggers
CREATE TRIGGER update_providers_updated_at BEFORE UPDATE ON providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_models_catalog_updated_at BEFORE UPDATE ON models_catalog
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_model_providers_updated_at BEFORE UPDATE ON model_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
