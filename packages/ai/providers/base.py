from __future__ import annotations

from abc import ABC, abstractmethod

from packages.ai.contracts import LLMRequest, LLMResult


class LLMProviderError(Exception):
    """Sanitized provider error safe to return or store."""


class LLMProviderConfigError(LLMProviderError):
    """Provider is not configured correctly."""


class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResult:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict:
        raise NotImplementedError
