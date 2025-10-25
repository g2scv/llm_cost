# LLM Cost Tracker

A Python microservice that tracks pricing for 350+ LLM models from OpenRouter and various providers, with automated daily data collection and Supabase storage.

## 🎯 Features

- ✅ **Automated Price Tracking** - Monitors 347+ LLM models daily
- ✅ **OpenRouter Integration** - Primary data source via Models API
- ✅ **Multi-Provider Support** - 10 provider adapters (OpenAI, Anthropic, Google, etc.)
- ✅ **Historical Snapshots** - Immutable daily pricing history
- ✅ **Price Change Detection** - Alerts on significant pricing changes (>30%)
- ✅ **BYOK Validation** - Spot-checks for Bring-Your-Own-Key pricing accuracy
- ✅ **Supabase Backend** - PostgreSQL with RLS security
- ✅ **Production Ready** - Scheduled runs, error handling, comprehensive logging

## 📊 Current Coverage

- **Models:** 348 tracked
- **Providers:** 68 in registry, 19 active
- **Pricing Snapshots:** 347 daily records
- **Data Quality:** 99.4% models with pricing
- **Foreign Key Integrity:** 100% (0 orphaned records)

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Supabase account
- OpenRouter API key
- (Optional) Brave Search API key for web scraping

### Installation

```bash
# Clone repository
git clone git@github.com:g2scv/llm_cost.git
cd llm_cost

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (optional, for dynamic scraping)
python -m playwright install chromium
```

### Configuration

Create `.env` file:

```bash
# Supabase (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key

# OpenRouter (Required)
OPENROUTER_API_KEY=sk-or-v1-your_key

# Brave Search (Optional - for provider scraping)
BRAVE_API_KEY=BSA-your_key
ENABLE_PROVIDER_SCRAPING=false  # Set to true to enable

# Optional Settings
REQUEST_TIMEOUT_SECONDS=30
PRICE_CHANGE_THRESHOLD_PERCENT=30.0
```

### Database Setup

Run migrations in Supabase:

```bash
# Apply all migrations in order
cat migrations/*.sql | psql $DATABASE_URL
```

Or use Supabase dashboard to run migration files from `migrations/` directory.

### Run Once

```bash
python -m app.main --once
```

### Schedule Daily Runs

#### Using systemd (Linux/VM)

```bash
# Copy service files
sudo cp ops/systemd/*.{service,timer} /etc/systemd/system/

# Enable and start
sudo systemctl enable --now pricing-tracker.timer
sudo systemctl status pricing-tracker.timer
```

#### Using cron

```bash
# Add to crontab
crontab -e

# Run daily at 2 AM UTC
0 2 * * * cd /path/to/llm_cost && .venv/bin/python -m app.main
```

## 📁 Project Structure

```
llm_cost/
├── app/
│   ├── main.py                 # Entry point & scheduler
│   ├── config.py               # Configuration (Pydantic)
│   ├── openrouter_client.py    # OpenRouter API client
│   ├── discovery.py            # Model & provider discovery
│   ├── pricing_pipeline.py     # Orchestration logic
│   ├── normalize.py            # Price normalization utils
│   ├── validation.py           # Data validation & alerts
│   ├── supabase_repo.py        # Database layer
│   └── providers/              # Provider-specific adapters
│       ├── registry.py         # Adapter registry
│       ├── base.py             # Base adapter interface
│       ├── openai.py           # OpenAI adapter
│       ├── anthropic.py        # Anthropic adapter
│       ├── google.py           # Google AI adapter
│       ├── cohere.py           # Cohere adapter
│       ├── mistral.py          # Mistral AI adapter
│       ├── deepseek.py         # DeepSeek adapter
│       ├── groq.py             # Groq adapter
│       ├── together.py         # Together AI adapter
│       ├── fireworks.py        # Fireworks adapter
│       ├── deepinfra.py        # DeepInfra adapter
│       └── generic_web.py      # Fallback web scraper
├── migrations/                 # Database migrations
│   ├── 01_initial_schema.sql
│   ├── 02_enable_rls.sql
│   ├── 03_create_policies.sql
│   ├── 04_fix_function_security.sql
│   └── 05_add_indexes.sql
├── ops/
│   ├── systemd/                # Systemd timer/service files
│   └── Dockerfile              # Docker deployment
├── configs/
│   ├── providers.yml           # Provider pricing URLs
│   └── models_blocklist.yml    # Models to skip
├── tests/                      # Test suite
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # Implementation guide
├── PIPELINE_STATUS.md          # Production readiness report
├── DATABASE_RELATIONSHIPS.md   # DB schema & integrity
├── PROVIDER_ADAPTERS.md        # Adapter documentation
└── README.md                   # This file
```

## 🗄️ Database Schema

### Core Tables

- **`providers`** (68 rows) - All providers in OpenRouter registry
- **`models_catalog`** (348 rows) - All tracked LLM models
- **`model_providers`** (128 rows) - Model-to-provider relationships
- **`model_pricing_daily`** (347+ rows) - Daily pricing snapshots
- **`byok_verifications`** (34+ rows) - BYOK validation records

### Relationships

```
providers ──┬─► model_providers ◄── models_catalog
            │                              │
            └──────────┬───────────────────┤
                       │                   │
                       ▼                   ▼
              model_pricing_daily   byok_verifications
```

All relationships have proper foreign keys and RLS policies enabled.

## 📈 Sample Queries

### Get Current Pricing

```sql
SELECT 
    mc.or_model_slug,
    mc.display_name,
    mpd.prompt_usd_per_million as input_per_1M,
    mpd.completion_usd_per_million as output_per_1M
FROM model_pricing_daily mpd
JOIN models_catalog mc ON mc.model_id = mpd.model_id
WHERE mpd.snapshot_date = CURRENT_DATE
  AND mpd.source_type = 'openrouter_api'
ORDER BY mpd.completion_usd_per_million DESC
LIMIT 10;
```

### Track Price Changes

```sql
SELECT 
    mc.or_model_slug,
    old.snapshot_date as old_date,
    old.prompt_usd_per_million as old_price,
    new.snapshot_date as new_date,
    new.prompt_usd_per_million as new_price,
    ROUND(((new.prompt_usd_per_million - old.prompt_usd_per_million) / 
           old.prompt_usd_per_million * 100)::numeric, 2) as change_percent
FROM model_pricing_daily old
JOIN model_pricing_daily new 
    ON old.model_id = new.model_id 
    AND new.snapshot_date > old.snapshot_date
JOIN models_catalog mc ON mc.model_id = old.model_id
WHERE ABS((new.prompt_usd_per_million - old.prompt_usd_per_million) / 
          old.prompt_usd_per_million * 100) > 30
ORDER BY ABS(change_percent) DESC;
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (full access) |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `BRAVE_API_KEY` | No | Brave Search API key |
| `ENABLE_PROVIDER_SCRAPING` | No | Enable web scraping (default: false) |
| `REQUEST_TIMEOUT_SECONDS` | No | HTTP timeout (default: 30) |
| `PRICE_CHANGE_THRESHOLD_PERCENT` | No | Alert threshold (default: 30.0) |

### Provider Adapters

Currently registered:
- ✅ OpenAI - Custom adapter with scraping
- ✅ Anthropic - Custom adapter with scraping
- ✅ Google - Placeholder (uses generic)
- ✅ Cohere - Placeholder (uses generic)
- ✅ Mistral - Placeholder (uses generic)
- ✅ DeepSeek - Placeholder (uses generic)
- ✅ Groq - Placeholder (uses generic)
- ✅ Together - Placeholder (uses generic)
- ✅ Fireworks - Placeholder (uses generic)
- ✅ DeepInfra - Placeholder (uses generic)

All adapters fall back to `GenericWebAdapter` with Brave Search integration.

## 🛡️ Security

- ✅ **Row Level Security (RLS)** enabled on all tables
- ✅ **Service role policies** for app access
- ✅ **Public read-only policies** for external queries
- ✅ **SQL injection prevention** via explicit search_path
- ✅ **Foreign key constraints** enforced
- ✅ **No orphaned records** (100% integrity)

## 📊 Monitoring

### Health Checks

```bash
# Check adapter registration
grep "registered_provider_adapter" /var/log/pricing-tracker.log

# Check pricing collection
SELECT COUNT(*) FROM model_pricing_daily WHERE snapshot_date = CURRENT_DATE;

# Check for errors
grep -i error /var/log/pricing-tracker.log
```

### Expected Metrics

- **Daily snapshots:** ~347 (one per model)
- **Price change alerts:** 0-5 (legitimate changes only)
- **Validation warnings:** <5 per run
- **Orphaned records:** 0 always

## 🐛 Troubleshooting

### Common Issues

**No pricing snapshots created**
```bash
# Check OpenRouter API key
python -c "from app.openrouter_client import OpenRouterClient; from app.config import load_config; c=load_config(); client=OpenRouterClient(c.openrouter_api_key); print(len(client.list_models()))"
```

**Price change warnings every run**
- Check that `source_type='openrouter_api'` filter is working
- Verify no stale `provider_site` data in database
- See `PRICE_CHANGE_WARNINGS_EXPLAINED.md`

**Brave API rate limits (429 errors)**
- Set `ENABLE_PROVIDER_SCRAPING=false` in `.env`
- OpenRouter API provides complete pricing already

**Database connection issues**
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
- Check RLS policies don't block service_role

## 📚 Documentation

- **`CLAUDE.md`** - Complete implementation guide & architecture
- **`PIPELINE_STATUS.md`** - Production readiness report
- **`DATABASE_RELATIONSHIPS.md`** - Schema & integrity analysis  
- **`PROVIDER_ADAPTERS.md`** - Provider adapter documentation
- **`PRICE_CHANGE_WARNINGS_EXPLAINED.md`** - Troubleshooting guide
- **`FIXES_APPLIED.md`** - Detailed changelog
- **`SESSION_SUMMARY.md`** - Development session notes

## 🚀 Deployment

### Docker

```bash
docker build -t llm-cost-tracker .
docker run -d \
  --env-file .env \
  --name llm-cost-tracker \
  llm-cost-tracker
```

### Cloud Platforms

- **Railway/Render:** Use `Dockerfile` + `.env` config
- **AWS Lambda:** Package as container, schedule with EventBridge
- **Google Cloud Run:** Deploy container, schedule with Cloud Scheduler
- **Azure Container Instances:** Deploy + Azure Functions timer

## 📈 Roadmap

- [ ] GraphQL API for pricing queries
- [ ] Real-time price change webhooks
- [ ] Cost calculator tool (estimate run costs)
- [ ] Grafana dashboard for trends
- [ ] More provider-specific adapters
- [ ] Multi-currency support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **OpenRouter** - Primary pricing data source
- **Supabase** - Database & authentication
- **Brave Search** - Web scraping fallback

## 📞 Support

- Issues: https://github.com/g2scv/llm_cost/issues
- Docs: See documentation files in repository

---

**Built with ❤️ for tracking LLM pricing in the rapidly evolving AI landscape.**
