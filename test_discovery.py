#!/usr/bin/env python3
"""Test discovery process"""

from app.config import Config
from app.openrouter_client import OpenRouterClient
from app.supabase_repo import SupabaseRepo
from app.discovery import ModelDiscovery


def main():
    print("\n=== Testing Discovery ===\n")

    cfg = Config()
    or_client = OpenRouterClient(api_key=cfg.openrouter_api_key)
    repo = SupabaseRepo(url=cfg.supabase_url, service_key=cfg.supabase_service_key)
    discovery = ModelDiscovery(or_client, repo)

    # Test providers discovery
    print("1. Testing provider discovery...")
    try:
        providers = or_client.list_providers()
        print(f"   API returned {len(providers)} providers")
        if providers:
            print(f"   First provider: {providers[0]}")

        count = discovery.discover_providers()
        print(f"   ✅ Upserted {count} providers to DB")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()

    # Test models discovery
    print("\n2. Testing model discovery...")
    try:
        models = or_client.list_models()
        print(f"   API returned {len(models)} models")
        if models:
            print(f"   First model: {models[0].get('id')}")

        all_models, new_models = discovery.discover_models()
        print(f"   Total models: {len(all_models)}")
        print(f"   New models: {len(new_models)}")

        count = discovery.sync_models_to_db(all_models)
        print(f"   ✅ Synced {count} models to DB")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()

    # Check database
    print("\n3. Verifying database...")
    try:
        result = repo.client.table("providers").select("*", count="exact").execute()
        print(f"   Providers in DB: {result.count}")

        result = (
            repo.client.table("models_catalog").select("*", count="exact").execute()
        )
        print(f"   Models in DB: {result.count}")

        result = (
            repo.client.table("model_providers").select("*", count="exact").execute()
        )
        print(f"   Model-Provider links in DB: {result.count}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()

    print("\n=== Discovery Test Complete ===\n")


if __name__ == "__main__":
    main()
