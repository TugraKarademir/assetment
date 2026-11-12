"""Sağlayıcı fabrikası."""
from __future__ import annotations

from ..config import ModelSpec
from .base import LLMRequest, LLMResult, Provider, RetryableError


def provider_class(spec: ModelSpec) -> type[Provider]:
    if spec.provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider
    if spec.provider == "openai_compat":
        from .openai_provider import OpenAICompatProvider
        return OpenAICompatProvider
    if spec.provider == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider
    if spec.provider == "google":
        from .google_provider import GoogleProvider
        return GoogleProvider
    if spec.provider == "mock":
        from .mock_provider import MockProvider
        return MockProvider
    raise ValueError(f"Bilinmeyen sağlayıcı: {spec.provider}")


def make_provider(spec: ModelSpec) -> Provider:
    return provider_class(spec)(spec)


def effective_params(spec: ModelSpec) -> dict:
    """İstemci oluşturmadan (API anahtarı gerektirmeden) etkin parametreler."""
    return provider_class(spec).effective_params_for(spec)


__all__ = ["make_provider", "provider_class", "effective_params", "LLMRequest", "LLMResult", "Provider", "RetryableError"]
