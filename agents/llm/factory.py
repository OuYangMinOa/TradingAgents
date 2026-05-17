from .base import BaseLLMProvider


def create_provider(provider: str, model: str, **api_keys: str) -> BaseLLMProvider:
    """Create an LLM provider from config.

    Usage:
        llm = create_provider(
            provider=settings.llm_provider,
            model=settings.llm_model,
            gemini_api_key=settings.gemini_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            openai_api_key=settings.openai_api_key,
        )

    To switch providers: change LLM_PROVIDER and LLM_MODEL in .env.
    No code changes required.
    """
    match provider.lower():
        case "gemini":
            from .gemini import GeminiProvider
            key = api_keys.get("gemini_api_key", "")
            if not key:
                raise ValueError("GEMINI_API_KEY is required for gemini provider")
            return GeminiProvider(api_key=key, model=model)

        case "claude" | "anthropic":
            from .claude import ClaudeProvider
            key = api_keys.get("anthropic_api_key", "")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY is required for claude provider")
            return ClaudeProvider(api_key=key, model=model)

        case "openai":
            from .openai_provider import OpenAIProvider
            key = api_keys.get("openai_api_key", "")
            if not key:
                raise ValueError("OPENAI_API_KEY is required for openai provider")
            return OpenAIProvider(api_key=key, model=model)

        case _:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                "Supported: gemini | claude | openai"
            )


def create_provider_from_settings() -> BaseLLMProvider:
    """Convenience: create provider directly from config.settings."""
    from config import settings
    return create_provider(
        provider=settings.llm_provider,
        model=settings.llm_model,
        gemini_api_key=settings.gemini_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
    )
