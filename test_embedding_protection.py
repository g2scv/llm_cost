#!/usr/bin/env python3
"""Test that text-embedding-3-large is always protected from deactivation"""

from app.backend_sync import BackendSync


def test_protected_models():
    """Verify that text-embedding-3-large is in the protected list"""

    assert "openai/text-embedding-3-large" in BackendSync.ALWAYS_ACTIVE_MODELS
    print("✅ text-embedding-3-large is in ALWAYS_ACTIVE_MODELS")


def test_deactivation_filtering():
    """Test that protected models are filtered from deactivation list"""

    # Simulate missing models
    existing_ids = {
        "openai/text-embedding-3-large",
        "openai/gpt-4",
        "anthropic/claude-3-opus",
    }

    current_ids = {
        "openai/gpt-4"  # Only GPT-4 in current sync
    }

    # Calculate missing (models that exist but weren't synced)
    missing_ids = list(existing_ids - current_ids)
    print(f"Missing IDs before filtering: {missing_ids}")

    # Filter out protected models (simulate the logic in finalize())
    protected_missing = [
        mid for mid in missing_ids if mid in BackendSync.ALWAYS_ACTIVE_MODELS
    ]
    filtered_missing = [
        mid for mid in missing_ids if mid not in BackendSync.ALWAYS_ACTIVE_MODELS
    ]

    print(f"Protected models (won't deactivate): {protected_missing}")
    print(f"Will deactivate: {filtered_missing}")

    # Assertions
    assert "openai/text-embedding-3-large" in protected_missing, (
        "text-embedding-3-large should be in protected list"
    )

    assert "openai/text-embedding-3-large" not in filtered_missing, (
        "text-embedding-3-large should NOT be in deactivation list"
    )

    assert "anthropic/claude-3-opus" in filtered_missing, (
        "claude-3-opus should be in deactivation list"
    )

    print("✅ Deactivation filtering works correctly")


if __name__ == "__main__":
    test_protected_models()
    test_deactivation_filtering()
    print("\n✅ All tests passed!")
