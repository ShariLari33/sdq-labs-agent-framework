from __future__ import annotations

from packages.ai.contracts import LLMRequest
from packages.ai.providers.base import BaseLLMProvider, LLMProviderError
from packages.ai.providers.mock import MockProvider
from packages.ai.providers.openai_provider import OpenAIProvider


class LLMGateway:
    def __init__(self, providers: list[BaseLLMProvider] | None = None):
        providers = providers or [MockProvider(), OpenAIProvider()]
        self.providers = {provider.provider_name: provider for provider in providers}

    def get_provider(self, provider_name: str) -> BaseLLMProvider:
        provider = self.providers.get(provider_name)
        if not provider:
            raise LLMProviderError(f"Unknown LLM provider: {provider_name}")
        return provider

    def generate(self, provider_name: str, request: LLMRequest):
        return self.get_provider(provider_name).generate(request)

    def health(self) -> dict:
        return {
            "providers": {
                name: provider.health_check()
                for name, provider in self.providers.items()
            }
        }
