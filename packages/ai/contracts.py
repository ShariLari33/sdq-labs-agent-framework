from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class LLMCost:
    currency: str = "USD"
    estimated_amount: float | None = None


@dataclass
class LLMResult:
    provider: str
    model: str
    text: str
    usage: LLMUsage
    cost: LLMCost
    latency_ms: int
    provider_response_id: str | None = None
    raw_metadata: dict = field(default_factory=dict)
