#!/bin/bash
set -e

echo "==================================="
echo "LLM Cost Scraper - Docker Container"
echo "==================================="
echo ""

# Check required environment variables
if [ -z "$SUPABASE_URL" ]; then
    echo "ERROR: SUPABASE_URL environment variable is required"
    exit 1
fi

if [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "ERROR: SUPABASE_SERVICE_KEY environment variable is required"
    exit 1
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "ERROR: OPENROUTER_API_KEY environment variable is required"
    exit 1
fi

echo "✅ Environment variables validated"
echo ""

# Optional backend sync check
if [ -n "$BACKEND_SUPABASE_URL" ] && [ -n "$BACKEND_SUPABASE_SERVICE_KEY" ]; then
    echo "✅ Backend sync enabled"
    export BACKEND_SYNC_ENABLED=true
else
    echo "⚠️  Backend sync disabled (no backend credentials)"
    export BACKEND_SYNC_ENABLED=false
fi

echo ""
echo "Starting scheduler..."
echo "Run frequency: Every ${RUN_INTERVAL_HOURS:-24} hours"
echo ""

# Run the scheduler
exec python -m app.scheduler
