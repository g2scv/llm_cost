# Docker Quick Start - 5 Minutes to Deploy

This is the fastest way to get the LLM Cost Scraper running in Docker.

---

## Step 1: Configure (2 minutes)

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required: Pricing Database
SUPABASE_URL=https://your-pricing-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...your-service-key

# Required: Backend Database (for auto-sync)
BACKEND_SUPABASE_URL=https://your-backend-project.supabase.co
BACKEND_SUPABASE_SERVICE_KEY=eyJhbGc...your-backend-service-key

# Required: OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...your-openrouter-key

# Optional: Set default embedding model
DEFAULT_EMBEDDING_MODEL_ID=openai/text-embedding-3-large
```

---

## Step 2: Deploy (1 minute)

```bash
# Start container
docker-compose up -d

# View logs
docker-compose logs -f llm-cost-scraper
```

---

## Step 3: Verify (2 minutes)

Watch the logs for success:

```bash
docker-compose logs -f
```

**Look for:**
```
✅ scheduler_started interval_hours=24
✅ running_pricing_pipeline
✅ checking_for_missing_models_in_backend
✅ scheduler_iteration_completed duration_seconds=45.2
```

**Check your backend database:**

```sql
SELECT COUNT(*) FROM llm_models WHERE is_active = true;
-- Expected: 300+ models

SELECT * FROM llm_models 
WHERE model_id = 'openai/text-embedding-3-large';
-- Should show: $0.13 input, $0.065 output per 1M tokens
```

---

## What Happens Next?

The container will now:

1. ✅ Run every 24 hours automatically
2. ✅ Check for missing models in your backend
3. ✅ Auto-fill any missing models
4. ✅ Keep `text-embedding-3-large` always active
5. ✅ Update pricing for all models

---

## Common Commands

```bash
# View logs
docker-compose logs -f

# Stop container
docker-compose down

# Restart container
docker-compose restart

# Run manually (single iteration)
docker-compose exec llm-cost-scraper python -m app.main --once

# Check status
docker-compose ps
```

---

## Troubleshooting

### Container won't start?

```bash
# Check logs for error
docker-compose logs llm-cost-scraper

# Verify .env file exists
ls -la .env

# Check required variables are set
docker-compose config | grep SUPABASE_URL
```

### No models syncing?

```bash
# Verify backend credentials
docker-compose exec llm-cost-scraper python -c "
from app.config import load_config
config = load_config()
print('Backend:', config.backend_supabase_url)
"

# Force a sync
docker-compose exec llm-cost-scraper python -m app.main --once
```

### Need to change schedule?

Edit `.env`:
```env
RUN_INTERVAL_HOURS=12  # Run every 12 hours instead of 24
```

Then restart:
```bash
docker-compose restart
```

---

## Next Steps

📖 **Full documentation:** See [README-DOCKER.md](./README-DOCKER.md)

🔧 **Configuration options:** See [.env.example](./.env.example)

🏗️ **Architecture:** See [CLAUDE.md](./CLAUDE.md)

---

That's it! Your LLM cost scraper is now running and will automatically keep your backend `llm_models` table up to date. 🚀
