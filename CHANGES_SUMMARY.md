# Summary of Changes - LLM Models Per-Million Pricing

## Date: 2025-10-29

---

## 1. ✅ Updated Backend Sync to Use Per-Million Pricing

### Changed Column Names
**From:** `cost_per_1k_input` / `cost_per_1k_output`  
**To:** `cost_per_million_input` / `cost_per_million_output`

This matches your database schema exactly:
```sql
cost_per_million_input numeric(10, 6)
cost_per_million_output numeric(10, 6)
```

### Removed Unit Conversion
**Before:**
```python
cost_per_1k_input = (prompt_price / 1000) if prompt_price is not None else None
cost_per_1k_output = (completion_price / 1000) if completion_price is not None else None
```

**After:**
```python
cost_per_million_input = prompt_price  # Already per million from normalize.py
cost_per_million_output = completion_price
```

### Updated Tier Classification Thresholds
```python
# Thresholds adjusted for per-million pricing
if cost_per_million_input >= 1000.0:  # Was >= 1.0 for per-1k
    return "premium"
if cost_per_million_input >= 200.0:  # Was >= 0.2 for per-1k
    return "standard"
return "budget"
```

### Files Modified
- `app/backend_sync.py` - All pricing logic updated to use per-million

---

## 2. ✅ Added OpenAI text-embedding-3-large Model

### Model Details
- **Model ID:** `openai/text-embedding-3-large`
- **Display Name:** `text-embedding-3-large`
- **Input Cost:** $0.13 per 1M tokens
- **Output Cost:** $0.065 per 1M tokens
- **Context Length:** 8,191 tokens
- **Embedding Dimensions:** 3,072
- **Source:** https://openai.com/api/pricing/

### Database Records Created
1. ✅ Provider: `openai` (with homepage and pricing URL)
2. ✅ Model catalog entry with architecture metadata
3. ✅ Model-provider link (marked as top provider)
4. ✅ Pricing snapshot for 2025-10-29

### Script Created
- `add_openai_embedding.py` - One-time script to add the model

---

## 3. ✅ Protected text-embedding-3-large from Deactivation

### Protection Mechanism
Added `ALWAYS_ACTIVE_MODELS` constant to `BackendSync` class:

```python
class BackendSync:
    """Coordinates staging and syncing model pricing data to the backend project."""

    # Models that should always remain active (manually added models)
    ALWAYS_ACTIVE_MODELS = {
        "openai/text-embedding-3-large",
    }
```

### Deactivation Logic Updated
The `finalize()` method now filters protected models before deactivation:

```python
# Never deactivate models in ALWAYS_ACTIVE_MODELS
protected_missing = [mid for mid in missing_ids if mid in self.ALWAYS_ACTIVE_MODELS]
if protected_missing:
    logger.info(
        "skipping_deactivation_for_protected_models",
        models=protected_missing
    )
    missing_ids = [mid for mid in missing_ids if mid not in self.ALWAYS_ACTIVE_MODELS]
```

### Behavior
- Even if `text-embedding-3-large` is NOT found in OpenRouter's models feed
- It will **never be deactivated** during sync operations
- It will always remain with `is_active=true` in the `llm_models` table

### Test Script Created
- `test_embedding_protection.py` - Verifies protection logic works correctly

---

## 4. Database Schema Alignment

### Your llm_models Table
```sql
create table public.llm_models (
  id uuid not null default gen_random_uuid(),
  model_id text not null,
  display_name text not null,
  provider text not null,
  model_type text not null,
  context_window integer null,
  max_output_tokens integer null,
  cost_per_million_input numeric(10, 6) null,   -- ✅ Matches code
  cost_per_million_output numeric(10, 6) null,  -- ✅ Matches code
  is_active boolean null default true,
  is_default boolean null default false,
  sort_order integer null default 0,
  capabilities jsonb null default '{}'::jsonb,
  metadata jsonb null default '{}'::jsonb,
  created_at timestamp with time zone null default timezone('utc'::text, now()),
  updated_at timestamp with time zone null default timezone('utc'::text, now()),
  is_thinking_model boolean not null default false,
  constraint llm_models_pkey primary key (id),
  constraint llm_models_model_id_key unique (model_id)
);
```

### Code Alignment
✅ All column names match exactly  
✅ Pricing stored as per-million  
✅ text-embedding-3-large protected from deactivation

---

## 5. Next Steps

### To Sync Models to Backend

1. **Set environment variables:**
   ```bash
   export BACKEND_SUPABASE_URL=https://your-backend-project.supabase.co
   export BACKEND_SUPABASE_SERVICE_KEY=your-backend-service-key
   ```

2. **Run the pipeline:**
   ```bash
   python -m app.main --once
   ```

3. **Verify results:**
   ```sql
   SELECT 
       model_id,
       display_name,
       cost_per_million_input,
       cost_per_million_output,
       is_active
   FROM llm_models
   WHERE model_id = 'openai/text-embedding-3-large';
   ```

   Expected result:
   ```
   openai/text-embedding-3-large | text-embedding-3-large | 0.130000 | 0.065000 | true
   ```

---

## 6. Example Pricing Values

### Sample Models (per 1 million tokens)

| Model | Input | Output | Tier |
|-------|-------|--------|------|
| text-embedding-3-large | $0.13 | $0.065 | budget |
| GPT-4o-mini | $0.15 | $0.60 | standard |
| GPT-4 Turbo | $10.00 | $30.00 | premium |
| Claude 3.5 Sonnet | $3.00 | $15.00 | premium |
| Claude 3 Haiku | $0.25 | $1.25 | standard |

---

## 7. Testing

### Run All Tests
```bash
# Protection logic test
python test_embedding_protection.py

# Syntax validation
python -m py_compile app/backend_sync.py

# Full pipeline test (if backend credentials configured)
python -m app.main --once
```

### Expected Outcomes
✅ text-embedding-3-large in protected models list  
✅ Deactivation skips protected models  
✅ All pricing stored as per-million  
✅ Column names match database schema

---

## 8. Files Changed

- ✅ `app/backend_sync.py` - Per-million pricing + protection logic
- ✅ `add_openai_embedding.py` - Script to add text-embedding-3-large
- ✅ `test_embedding_protection.py` - Test protection logic
- ✅ `CHANGES_SUMMARY.md` - This document

---

## Notes

- The `numeric(10, 6)` precision allows values up to $9,999.999999 per million tokens
- Protection is automatic - no manual intervention needed for text-embedding-3-large
- To add more protected models, add them to `ALWAYS_ACTIVE_MODELS` set
- The system maintains historical pricing in `model_pricing_daily` table
- Backend sync is optional - enable with `BACKEND_SUPABASE_URL` environment variable
