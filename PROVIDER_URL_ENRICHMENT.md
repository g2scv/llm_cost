# Provider URL Enrichment

## Summary

Successfully enriched provider records with homepage and pricing URLs.

## Results

```
✅ Total providers: 68
✅ Providers with homepage URL: 63 (92.6%)
✅ Providers with pricing URL: 63 (92.6%)
❌ Providers without URLs: 5 (7.4%)
```

## Implementation

### URL Derivation Strategy

1. **Homepage URL**: Extracted from OpenRouter Providers API fields
   - Priority order: `privacy_policy_url` → `terms_of_service_url` → `status_page_url`
   - Extract base domain from any available URL
   - Example: `https://openai.com/policies/privacy-policy/` → `https://openai.com`

2. **Pricing URL**: Derived using pattern matching
   - Known providers use hardcoded pricing URLs (OpenAI, Anthropic, etc.)
   - Unknown providers default to `{homepage}/pricing`

### Code Changes

**File**: `app/discovery.py`

Added two helper methods:

```python
def _derive_homepage_url(self, provider: Dict[str, Any]) -> str | None:
    """Extract homepage from privacy/terms/status URLs"""
    from urllib.parse import urlparse
    
    for url_field in ["privacy_policy_url", "terms_of_service_url", "status_page_url"]:
        url = provider.get(url_field)
        if url:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
    return None

def _derive_pricing_url(self, slug: str, homepage_url: str | None) -> str | None:
    """Derive pricing URL from known patterns or default"""
    if not homepage_url:
        return None
    
    # Known patterns for major providers
    pricing_patterns = {
        "openai": "https://openai.com/api/pricing/",
        "anthropic": "https://www.anthropic.com/pricing",
        "cohere": "https://cohere.com/pricing",
        "google": "https://ai.google.dev/pricing",
        "mistral": "https://mistral.ai/technology/#pricing",
        "groq": "https://groq.com/pricing/",
        # ... 12 patterns total
    }
    
    return pricing_patterns.get(slug, f"{homepage_url.rstrip('/')}/pricing")
```

## Sample Results

### Providers WITH URLs

| Provider | Homepage | Pricing |
|----------|----------|---------|
| OpenAI | https://openai.com | https://openai.com/api/pricing/ |
| Anthropic | https://www.anthropic.com | https://www.anthropic.com/pricing |
| Mistral | https://mistral.ai | https://mistral.ai/technology/#pricing |
| Cohere | https://www.cohere.com | https://cohere.com/pricing |
| Groq | https://groq.com | https://groq.com/pricing/ |
| DeepInfra | https://deepinfra.com | https://deepinfra.com/pricing |
| Cerebras | https://www.cerebras.ai | https://www.cerebras.ai/pricing |
| Fireworks | https://fireworks.ai | https://fireworks.ai/pricing |

### Providers WITHOUT URLs

These 5 providers don't have any URL fields in the OpenRouter API:

1. **z-ai** (Z.AI)
2. **stealth** (Stealth)
3. **switchpoint** (Switchpoint)
4. **fake-provider** (FakeProvider) - likely a test provider
5. **cirrascale** (Cirrascale)

## Known Pricing URL Patterns

The system includes hardcoded patterns for these providers:

```python
pricing_patterns = {
    "openai": "https://openai.com/api/pricing/",
    "anthropic": "https://www.anthropic.com/pricing",
    "cohere": "https://cohere.com/pricing",
    "google": "https://ai.google.dev/pricing",
    "mistral": "https://mistral.ai/technology/#pricing",
    "groq": "https://groq.com/pricing/",
    "together": "https://www.together.ai/pricing",
    "fireworks": "https://fireworks.ai/pricing",
    "deepinfra": "https://deepinfra.com/pricing",
    "replicate": "https://replicate.com/pricing",
    "perplexity": "https://www.perplexity.ai/hub/pricing",
    "cerebras": "https://www.cerebras.ai/pricing",
}
```

## Benefits

1. **Auditability**: Source URLs are now available for manual verification
2. **Provider Adapters**: Can use these URLs for web scraping pricing data
3. **Documentation**: Better context for each provider
4. **Fallback Sources**: When OpenRouter API pricing is missing, can scrape provider sites

## Next Steps (Optional)

1. **Manually add URLs** for the 5 providers without URLs if needed
2. **Validate pricing URLs**: Test HTTP requests to ensure URLs are valid
3. **Add more patterns**: As new providers are added, update the `pricing_patterns` dict
4. **Web scraping enhancement**: Use pricing URLs in provider adapters

## Verification

Run this query to check provider URLs:

```python
from app.config import load_config
from app.supabase_repo import SupabaseRepo

cfg = load_config()
repo = SupabaseRepo(cfg.supabase_url, cfg.supabase_service_key)

providers = repo.client.table('providers').select(
    'slug, display_name, homepage_url, pricing_url'
).execute().data

for p in providers:
    print(f"{p['slug']:20s} | {p['homepage_url'] or '(none)'}")
```
