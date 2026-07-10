import os
import time

from packages.ai.contracts import LLMCost, LLMRequest, LLMResult, LLMUsage
from packages.ai.providers.base import (
    BaseLLMProvider,
    LLMProviderConfigError,
    LLMProviderError,
)


class OpenAIProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "openai"

    def _client(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise LLMProviderConfigError("OpenAI provider is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMProviderConfigError("OpenAI SDK is not installed") from exc
        return OpenAI()

    def generate(self, request: LLMRequest) -> LLMResult:
        started = time.monotonic()
        client = self._client()
        args = {
            "model": request.model,
            "instructions": request.system_prompt,
            "input": request.user_prompt,
        }

        if request.max_output_tokens is not None:
            args["max_output_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            args["temperature"] = request.temperature

        try:
            try:
                response = client.responses.create(**args)
            except TypeError:
                args.pop("temperature", None)
                response = client.responses.create(**args)
        except LLMProviderConfigError:
            raise
        except Exception as exc:
            raise LLMProviderError(type(exc).__name__) from exc

        usage = getattr(response, "usage", None)
        input_tokens = self._usage_value(usage, "input_tokens")
        output_tokens = self._usage_value(usage, "output_tokens")
        total_tokens = self._usage_value(usage, "total_tokens")

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return LLMResult(
            provider=self.provider_name,
            model=request.model,
            text=getattr(response, "output_text", "") or "",
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            cost=LLMCost(estimated_amount=None),
            latency_ms=int((time.monotonic() - started) * 1000),
            provider_response_id=getattr(response, "id", None),
            raw_metadata={},
        )

    def health_check(self) -> dict:
        configured = bool(os.getenv("OPENAI_API_KEY"))
        return {"configured": configured, "healthy": configured}

    def _usage_value(self, usage, name):
        if usage is None:
            return None
        if isinstance(usage, dict):
            return usage.get(name)
        return getattr(usage, name, None)
