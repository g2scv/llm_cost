# Docker Deployment Guide - LLM Cost Scraper

This guide explains how to deploy the LLM Cost Scraper as a Docker container that runs every 24 hours and automatically syncs missing models to your backend.

---

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- Supabase account with two projects:
  - **Pricing Database** (stores model catalog and pricing snapshots)
  - **Backend Database** (contains `llm_models` table for your application)
- OpenRouter API key

### 2. Configuration

Create a `.env` file in the project root:

```bash
# Copy the example
cp .env.example .env

# Edit with your credentials
nano .env
```

**Minimum required variables:**

```env
# Pricing Database (required)
SUPABASE_URL=https://your-pricing-project.supabase.co
SUPABASE_SERVICE_KEY=your-pricing-service-key

# Backend Database (required for auto-sync)
BACKEND_SUPABASE_URL=https://your-backend-project.supabase.co
BACKEND_SUPABASE_SERVICE_KEY=your-backend-service-key

# OpenRouter (required)
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key

# Scheduler settings (optional)
RUN_INTERVAL_HOURS=24
RUN_ON_STARTUP=true
CHECK_MISSING_MODELS=true
```

### 3. Deploy

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f llm-cost-scraper

# Check status
docker-compose ps
```

---

## Features

### ✅ 24-Hour Scheduled Runs

The container runs the pricing pipeline automatically every 24 hours:

1. **Fetch Models** - Gets all models from OpenRouter API
2. **Collect Pricing** - Gathers pricing data (per-million tokens)
3. **Sync to Backend** - Updates your `llm_models` table
4. **Check Missing** - Detects and auto-fills any missing models

### ✅ Auto-Fill Missing Models

The scheduler checks your backend `llm_models` table before each run:

- Compares models in pricing database vs backend
- Finds models with recent pricing data (last 7 days)
- Automatically syncs any missing models to backend
- Ensures `text-embedding-3-large` is always active (protected)

### ✅ Persistent Logging

Logs are stored in `./logs` directory:

```bash
# View logs from host
tail -f logs/app.log

# View container logs
docker-compose logs -f
```

### ✅ Health Monitoring

Health checks run every 5 minutes:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' llm-cost-scraper
```

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_INTERVAL_HOURS` | `24` | Hours between pipeline runs |
| `RUN_ON_STARTUP` | `true` | Run immediately on container start |
| `AUTO_SYNC_BACKEND` | `true` | Enable backend sync |
| `CHECK_MISSING_MODELS` | `true` | Auto-detect and fill missing models |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MAX_PARALLEL_MODELS` | `10` | Concurrent model processing |
| `PRICE_CHANGE_THRESHOLD_PERCENT` | `30.0` | Alert threshold for price changes |

### Scheduler Behavior

#### Run on Startup = true (default)
```
Container starts → Run immediately → Wait 24h → Run again → ...
```

#### Run on Startup = false
```
Container starts → Wait 24h → Run → Wait 24h → Run again → ...
```

---

## Docker Commands

### Basic Operations

```bash
# Start container
docker-compose up -d

# Stop container
docker-compose down

# Restart container
docker-compose restart

# View logs (live)
docker-compose logs -f llm-cost-scraper

# View last 100 lines
docker-compose logs --tail=100 llm-cost-scraper

# Execute command in container
docker-compose exec llm-cost-scraper python -m app.main --once
```

### Debugging

```bash
# Enter container shell
docker-compose exec llm-cost-scraper bash

# Check environment variables
docker-compose exec llm-cost-scraper env | grep SUPABASE

# Test database connection
docker-compose exec llm-cost-scraper python -c "
from app.config import load_config
from app.supabase_repo import SupabaseRepo
config = load_config()
repo = SupabaseRepo(config.supabase_url, config.supabase_service_key)
print(f'Connected! Found {len(repo.get_all_model_slugs())} models')
"

# Run pipeline manually (single run)
docker-compose exec llm-cost-scraper python -m app.main --once
```

### Maintenance

```bash
# Rebuild image (after code changes)
docker-compose build --no-cache

# View resource usage
docker stats llm-cost-scraper

# Clean up old images
docker image prune -a

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/
```

---

## Auto-Sync Logic

### How Missing Models are Detected

1. **Query Pricing DB** - Gets models with pricing snapshots in last 7 days
2. **Query Backend DB** - Gets all `model_id` values from `llm_models` table
3. **Calculate Difference** - Finds models in pricing DB but not in backend
4. **Log Results**:
   ```
   found_missing_models_in_backend count=15 models=['openai/gpt-4o', ...]
   ```
5. **Auto-Sync** - Pipeline syncs missing models during this run

### Protected Models

Some models are **always kept active** even if missing from OpenRouter:

- `openai/text-embedding-3-large` (manually added, always active)

To add more protected models, edit `app/backend_sync.py`:

```python
ALWAYS_ACTIVE_MODELS = {
    "openai/text-embedding-3-large",
    "your-custom/model-slug",  # Add here
}
```

---

## Monitoring

### Log Messages to Watch For

**✅ Success indicators:**
```
scheduler_started interval_hours=24
running_pricing_pipeline
found_missing_models_in_backend count=0
scheduler_iteration_completed duration_seconds=45.2
```

**⚠️ Warnings:**
```
backend_sync_disabled reason="no_credentials"
skipping_initial_run reason="run_on_startup=false"
```

**❌ Errors:**
```
scheduler_iteration_failed error="..."
failed_to_check_missing_models error="..."
```

### Metrics to Track

```bash
# Check last run time
docker-compose logs --tail=50 llm-cost-scraper | grep scheduler_iteration_completed

# Check for missing models
docker-compose logs --tail=100 llm-cost-scraper | grep missing_models

# Check sync status
docker-compose logs --tail=100 llm-cost-scraper | grep backend_sync
```

---

## Database Schema Requirements

### Backend Table (llm_models)

Your backend database must have this table:

```sql
create table public.llm_models (
  id uuid not null default gen_random_uuid(),
  model_id text not null,
  display_name text not null,
  provider text not null,
  model_type text not null,
  context_window integer null,
  max_output_tokens integer null,
  cost_per_million_input numeric(10, 6) null,
  cost_per_million_output numeric(10, 6) null,
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

### Verify Sync is Working

```sql
-- Check synced models count
SELECT COUNT(*) FROM llm_models WHERE is_active = true;

-- Check text-embedding-3-large
SELECT 
    model_id,
    display_name,
    cost_per_million_input,
    cost_per_million_output,
    is_active
FROM llm_models
WHERE model_id = 'openai/text-embedding-3-large';

-- Check recently updated models
SELECT 
    model_id,
    display_name,
    updated_at
FROM llm_models
ORDER BY updated_at DESC
LIMIT 10;
```

---

## Deployment Patterns

### Development

```bash
# Run with live logs
docker-compose up

# Run single iteration then exit
docker-compose run --rm llm-cost-scraper python -m app.main --once
```

### Production

```bash
# Run detached with restart policy
docker-compose up -d

# Enable auto-restart on system reboot
# (already configured in docker-compose.yml with restart: unless-stopped)
```

### Custom Schedule

To run every 6 hours instead of 24:

```env
RUN_INTERVAL_HOURS=6
```

Or use cron outside Docker:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/project && docker-compose exec -T llm-cost-scraper python -m app.main --once
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs llm-cost-scraper

# Common issues:
# 1. Missing environment variables
# 2. Invalid Supabase credentials
# 3. Port conflicts
```

### No Models Syncing

```bash
# Verify backend credentials
docker-compose exec llm-cost-scraper python -c "
from app.config import load_config
config = load_config()
print('Backend URL:', config.backend_supabase_url)
print('Key set:', bool(config.backend_supabase_service_key))
"

# Manually trigger sync
docker-compose exec llm-cost-scraper python -m app.main --once
```

### High Memory Usage

```bash
# Check current usage
docker stats llm-cost-scraper

# Reduce parallel processing in .env
MAX_PARALLEL_MODELS=5
```

### Schedule Not Running

```bash
# Check scheduler is running
docker-compose ps

# Check logs for scheduler messages
docker-compose logs --tail=50 llm-cost-scraper | grep scheduler

# Verify interval setting
docker-compose exec llm-cost-scraper env | grep RUN_INTERVAL
```

---

## Backup & Recovery

### Backup Container Configuration

```bash
# Backup .env file
cp .env .env.backup-$(date +%Y%m%d)

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# Export container config
docker inspect llm-cost-scraper > container-config-$(date +%Y%m%d).json
```

### Disaster Recovery

```bash
# Stop container
docker-compose down

# Restore .env
cp .env.backup-YYYYMMDD .env

# Rebuild and restart
docker-compose up -d --build

# Verify
docker-compose logs -f
```

---

## Performance Tuning

### Optimize for Speed

```env
# Increase parallelism (requires more memory)
MAX_PARALLEL_MODELS=20

# Disable provider scraping (faster, relies only on OpenRouter)
ENABLE_PROVIDER_SCRAPING=false
```

### Optimize for Reliability

```env
# Reduce parallelism (more stable)
MAX_PARALLEL_MODELS=5

# Increase timeout for slow connections
REQUEST_TIMEOUT_SECONDS=60
```

### Resource Limits

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'      # Increase CPU
      memory: 2G     # Increase RAM
```

---

## Security Best Practices

1. **Never commit .env file**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use secrets management** (production)
   - Docker secrets
   - HashiCorp Vault
   - AWS Secrets Manager

3. **Limit service account permissions**
   - Pricing DB: Read/Write on pricing tables only
   - Backend DB: Read/Write on `llm_models` table only

4. **Enable RLS** (Row Level Security) on Supabase tables

5. **Regular updates**
   ```bash
   git pull
   docker-compose build --no-cache
   docker-compose up -d
   ```

---

## Support

### Get Help

- **Logs**: `docker-compose logs -f`
- **Issues**: Check GitHub issues
- **Docs**: See main README.md and CLAUDE.md

### Common Questions

**Q: How do I change the schedule?**  
A: Set `RUN_INTERVAL_HOURS` in `.env`, then restart: `docker-compose restart`

**Q: Can I run multiple instances?**  
A: Yes, but ensure each has unique container names in `docker-compose.yml`

**Q: How do I add custom models?**  
A: Use `add_openai_embedding.py` as template, or add to protected list

**Q: What if OpenRouter API is down?**  
A: Container will retry next scheduled run. Check logs for errors.

---

## Example: Complete Deployment

```bash
# 1. Clone repository
git clone <repo-url>
cd cost_scraper

# 2. Configure environment
cp .env.example .env
nano .env  # Add your credentials

# 3. Build and start
docker-compose up -d

# 4. Verify it's working
docker-compose logs -f

# 5. Check backend sync after first run
# (wait for completion, usually 2-5 minutes)
docker-compose logs | grep "synced.*models"

# 6. Verify in database
# Run SQL query on backend Supabase:
# SELECT COUNT(*) FROM llm_models WHERE is_active = true;

# Expected: 300+ models synced
```

---

## Next Steps

1. ✅ Set up monitoring alerts (optional)
2. ✅ Configure backups (optional)
3. ✅ Review logs after first run
4. ✅ Verify data in `llm_models` table
5. ✅ Set up health check notifications

Happy scraping! 🚀
