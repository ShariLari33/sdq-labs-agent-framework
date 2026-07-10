import json
import time

from packages.ai.contracts import LLMCost, LLMRequest, LLMResult, LLMUsage
from packages.ai.providers.base import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, request: LLMRequest) -> LLMResult:
        started = time.monotonic()
        text = json.dumps(
            {
                "summary": "Mock provider completed the analysis.",
                "findings": [
                    "Mock finding: performance data was reviewed."
                ],
                "recommendations": [
                    "Mock recommendation: review high-spend areas first."
                ],
                "learning_candidates": [
                    {
                        "title": "Mock reusable performance insight",
                        "body": "Prioritize wasted spend and budget pacing in future analyses.",
                    }
                ],
                "approval_required": True,
            }
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        return LLMResult(
            provider=self.provider_name,
            model=request.model,
            text=text,
            usage=LLMUsage(input_tokens=0, output_tokens=0, total_tokens=0),
            cost=LLMCost(estimated_amount=0),
            latency_ms=latency_ms,
            provider_response_id=None,
            raw_metadata={"mock": True},
        )

    def health_check(self) -> dict:
        return {"configured": True, "healthy": True}
