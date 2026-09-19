"""Reviewed general-purpose model catalog; account access is not guaranteed.

Sources checked 2026-09-19:
https://developers.openai.com/api/docs/models
https://platform.claude.com/docs/en/models/overview
Specialised image, audio and restricted research models are not chat choices.
"""
CATALOG_DATE = "2026-09-19"
MODELS = [
    {"id": "gpt-6-astra", "name": "GPT-6 Astra", "provider": "openai", "description": "Flagship · complex reasoning", "tier": "Flagship"},
    {"id": "gpt-5.6-sol", "name": "GPT-5.6 Sol", "provider": "openai", "description": "Professional work", "tier": "Flagship"},
    {"id": "gpt-5.6-terra", "name": "GPT-5.6 Terra", "provider": "openai", "description": "Balanced intelligence and cost", "tier": "Balanced"},
    {"id": "gpt-5.6-luna", "name": "GPT-5.6 Luna", "provider": "openai", "description": "Fast, cost-conscious requests", "tier": "Fast"},
    {"id": "claude-fable-5-1", "name": "Claude Fable 5.1", "provider": "anthropic", "description": "Flagship · demanding reasoning", "tier": "Flagship"},
    {"id": "claude-opus-5", "name": "Claude Opus 5", "provider": "anthropic", "description": "Complex analysis and coding", "tier": "Flagship"},
    {"id": "claude-sonnet-5", "name": "Claude Sonnet 5", "provider": "anthropic", "description": "Balanced speed and intelligence", "tier": "Balanced"},
    {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "provider": "anthropic", "description": "Lightweight, quick answers", "tier": "Fast"},
]


def validate_model(provider, model):
    if not any(item["provider"] == provider and item["id"] == model for item in MODELS):
        raise ValueError("Model does not match the reviewed provider catalog")
