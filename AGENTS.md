# LLM Cost Tracker - AGENTS.md

## Overview
Automated daily scraping of OpenRouter model pricing with sync to g2scv backend's `llm_models` table.

**Status**: ✅ Fully Configured and Running
**Last Updated**: November 30, 2025

## Purpose
Tracks pricing for **text-only** LLM models from OpenRouter that support:
- `structured_outputs`
- `response_format`  
- `stop`
- `input_modalities=text`
- `output_modalities=text`

These parameters are **required** for g2scv's CV generation system. Vision, audio, and video models are excluded.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 LLM Cost Tracker (Daily @ 2 AM UTC)             │
├─────────────────────────────────────────────────────────────────┤
│ 1. Fetch models from OpenRouter with filtering:                 │
│    - supported_parameters=structured_outputs,response_format,stop│
│    - distillable=false                                          │
│    - input_modalities=text                                      │
│    - output_modalities=text                                     │
│                                                                 │
│ 2. Sync to local tables (Supabase):                            │
│    - providers (66 rows)                                        │
│    - models_catalog (172 rows)                                  │
│    - model_pricing_daily (daily snapshots)                      │
│                                                                 │
│ 3. Sync to g2scv backend llm_models table:                     │
│    - Upsert active models with pricing                          │
│    - Deactivate missing models                                  │
│    - Preserve default model settings                            │
└─────────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `app/config.py` | Configuration with model filtering options |
| `app/openrouter_client.py` | OpenRouter API client with filtering support |
| `app/discovery.py` | Model discovery with parameter filtering |
| `app/pricing_pipeline.py` | Main orchestration pipeline |
| `app/backend_sync.py` | Sync to g2scv llm_models table |
| `.env` | Environment configuration |

## Configuration

### Environment Variables (.env)

```bash
# Supabase (same project for tracking + backend)
SUPABASE_URL=https://wgesndovfwsilydpjsof.supabase.co
SUPABASE_SERVICE_KEY=...
BACKEND_SUPABASE_URL=https://wgesndovfwsilydpjsof.supabase.co
BACKEND_SUPABASE_SERVICE_KEY=...

# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-...

# Only include models that support structured_outputs, response_format, and stop
MODEL_FILTER_SUPPORTED_PARAMETERS=structured_outputs,response_format,stop
# Exclude distillable models
MODEL_FILTER_DISTILLABLE=false
# Text-only models (no vision, audio, video)
MODEL_FILTER_INPUT_MODALITIES=text
MODEL_FILTER_OUTPUT_MODALITIES=text

# Default models for backend
DEFAULT_CHAT_MODEL_ID=openai/gpt-oss-120b
DEFAULT_EMBEDDING_MODEL_ID=openai/text-embedding-3-large
```

## Systemd Timer

```bash
# Timer runs daily at 2 AM UTC
/etc/systemd/system/llm-cost-tracker.timer
/etc/systemd/system/llm-cost-tracker.service

# Check status
systemctl status llm-cost-tracker.timer

# Run manually
systemctl start llm-cost-tracker.service

# View logs
journalctl -u llm-cost-tracker.service
```

## Database Tables

### llm_cost Tables (Supabase)
- `providers` - OpenRouter provider registry
- `models_catalog` - Model metadata and capabilities
- `model_providers` - Model-to-provider relationships
- `model_pricing_daily` - Daily pricing snapshots (historical)
- `byok_verifications` - BYOK spot-check records

### g2scv Backend (llm_models)
Updated automatically with:
- `model_id` - OpenRouter model slug
- `display_name` - Human-readable name
- `cost_per_million_input/output` - Per-million token pricing
- `context_window` - Max context length
- `capabilities` - JSON with supports_tools, supports_vision, etc.
- `is_active` - Whether model is available
- `is_default` - Default model flag

## Manual Commands

```bash
cd /root/g2scv/llm_cost
source .venv/bin/activate

# Run once manually
python -m app.main --once

# Test OpenRouter filtering
python -c "
from app.config import load_config
from app.openrouter_client import OpenRouterClient
cfg = load_config()
client = OpenRouterClient(cfg.openrouter_api_key)
models = client.list_models(
    supported_parameters=cfg.model_filter_supported_parameters,
    distillable=cfg.model_filter_distillable
)
print(f'Found {len(models)} models')
"
```

## Current Model Coverage

| Metric | Count |
|--------|-------|
| Total providers | 66 |
| Total models (text-only, filtered) | 112 |
| Active in backend | 112 |
| Free tier models | ~10 |

## Model Filtering Logic

The OpenRouter API supports query parameters for filtering:
- `supported_parameters=structured_outputs,response_format,stop` - Only models supporting all three
- `distillable=false` - Exclude models that can be distilled

This ensures only **production-ready** models for CV generation are synced.

## Price Change Alerts

The pipeline detects price changes > 30% and logs warnings:
- Helps identify pricing anomalies
- Historical data in `model_pricing_daily` enables trend analysis

## Troubleshooting

### Timer not running
```bash
systemctl status llm-cost-tracker.timer
systemctl restart llm-cost-tracker.timer
journalctl -u llm-cost-tracker -n 50
```

### Missing models in backend
```bash
# Check what models were filtered out
python -c "
from app.openrouter_client import OpenRouterClient
import os
client = OpenRouterClient(os.environ['OPENROUTER_API_KEY'])
all_models = client.list_models()
filtered = client.list_models(
    supported_parameters='structured_outputs,response_format,stop',
    distillable=False
)
print(f'All: {len(all_models)}, Filtered: {len(filtered)}')
print(f'Excluded: {len(all_models) - len(filtered)}')
"
```

### Backend sync issues
```bash
# Check backend_sync.py logs
grep "backend_sync" /var/log/llm-cost-tracker.log
```

## Related Documentation
- [OpenRouter Models API](https://openrouter.ai/docs/api-reference/models/get-models)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/features/structured-outputs)
- `/root/g2scv/backend/docs/MODEL_SELECTION_API.md`
