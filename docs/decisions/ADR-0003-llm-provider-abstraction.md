# ADR-0003 — LLM Provider Abstraction

## Status
Accepted

## Context
SDQ Labs Agent Framework must support multiple language model providers without coupling workers, skills or orchestration logic to one vendor.

Supported providers may include:
- OpenAI
- Anthropic
- Google Gemini
- Qwen
- DeepSeek
- Local models
- Mock providers for testing

## Decision
All model calls must go through a provider-neutral interface.

Workers never instantiate provider SDK clients directly.

The Execution Planner resolves a model route. The LLM Gateway uses that route to select the correct provider adapter.

## Architecture

Task
↓
Execution Planner
↓
Model Route
↓
LLM Gateway
↓
Provider Adapter
↓
Standard LLM Result

## Provider Interface

Every provider adapter must implement:

- provider_name
- generate(request)
- health_check()

## Standard Request

{
  "model": "...",
  "system_prompt": "...",
  "user_prompt": "...",
  "temperature": null,
  "max_output_tokens": null,
  "metadata": {}
}

## Standard Result

{
  "provider": "...",
  "model": "...",
  "text": "...",
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null
  },
  "cost": {
    "currency": "USD",
    "estimated_amount": null
  },
  "latency_ms": 0,
  "provider_response_id": null,
  "raw_metadata": {}
}

## Security

- API keys are read only from environment variables.
- API keys are never stored in the database.
- API keys are never placed in prompts, events or logs.
- Provider errors must not expose credentials.
- Model calls must be auditable without storing secrets.

## Routing

Model names are configuration, not application logic.

The database model route determines:
- provider
- model
- sensitivity
- cost tier
- quality tier

## Initial Implementation

Version 0.1 includes:
- MockProvider
- OpenAIProvider
- LLMGateway

Future providers must implement the same interface.

## Consequences

Workers remain provider-independent.

Switching from OpenAI to Claude, Gemini or another compatible provider does not require changing skills or worker logic.
