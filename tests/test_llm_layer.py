import os
import unittest
from unittest.mock import Mock, patch

from packages.ai.contracts import LLMRequest
from packages.ai.gateway import LLMGateway
from packages.ai.providers.base import LLMProviderConfigError, LLMProviderError
from packages.ai.providers.mock import MockProvider
from packages.ai.providers.openai_provider import OpenAIProvider
from packages.execution.output_parser import normalize_llm_output
from packages.execution.prompt_builder import build_prompts


class LLMProviderTests(unittest.TestCase):
    def test_mock_provider_returns_deterministic_json(self):
        provider = MockProvider()
        result = provider.generate(
            LLMRequest(
                model="mock-model-v0",
                system_prompt="system",
                user_prompt="user",
            )
        )

        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "mock-model-v0")
        self.assertIn("Mock provider completed", result.text)
        self.assertEqual(result.usage.total_tokens, 0)

    def test_mock_provider_grounds_performance_analysis_in_summary(self):
        provider = MockProvider()
        result = provider.generate(
            LLMRequest(
                model="mock-model-v0",
                system_prompt="system",
                user_prompt="user",
                metadata={
                    "task_type": "performance_analysis",
                    "performance_summary": {
                        "period": {
                            "date_from": "2026-06-01",
                            "date_to": "2026-06-04",
                        },
                        "campaign_breakdown": [
                            {
                                "campaign_name": "Competitor Display",
                                "totals": {
                                    "impressions": 187200,
                                    "cost": 2116.45,
                                    "conversions": 0,
                                },
                                "metrics": {
                                    "ctr": 0.00383,
                                    "cost_per_conversion": None,
                                    "roas": 0,
                                },
                                "spend_share": 0.19,
                                "conversion_share": 0,
                            }
                        ],
                    },
                },
            )
        )

        output = normalize_llm_output(result.text)

        self.assertEqual(output["findings"][0]["campaign"], "Competitor Display")
        self.assertIn("spending without", output["findings"][0]["observation"])
        self.assertEqual(output["recommendations"][0]["priority"], "high")

    def test_unknown_provider_raises_clear_error(self):
        gateway = LLMGateway(providers=[MockProvider()])

        with self.assertRaises(LLMProviderError) as ctx:
            gateway.get_provider("missing")

        self.assertIn("Unknown LLM provider", str(ctx.exception))

    def test_provider_health_response(self):
        gateway = LLMGateway(providers=[MockProvider(), OpenAIProvider()])

        with patch.dict(os.environ, {}, clear=True):
            health = gateway.health()

        self.assertTrue(health["providers"]["mock"]["healthy"])
        self.assertFalse(health["providers"]["openai"]["configured"])
        self.assertFalse(health["providers"]["openai"]["healthy"])

    def test_missing_openai_api_key_raises_config_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMProviderConfigError):
                OpenAIProvider().generate(
                    LLMRequest(
                        model="gpt-test",
                        system_prompt="system",
                        user_prompt="user",
                    )
                )

    def test_openai_provider_error_does_not_leak_secret(self):
        response_client = Mock()
        response_client.responses.create.side_effect = Exception("sk-secret-value")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-secret-value"}):
            with patch.object(OpenAIProvider, "_client", return_value=response_client):
                with self.assertRaises(LLMProviderError) as ctx:
                    OpenAIProvider().generate(
                        LLMRequest(
                            model="gpt-test",
                            system_prompt="system",
                            user_prompt="user",
                        )
                    )

        self.assertNotIn("sk-secret-value", str(ctx.exception))


class ExecutionHelperTests(unittest.TestCase):
    def test_prompt_builder_separates_memory_and_rules(self):
        execution_package = {
            "capability": {
                "name": "Performance Analysis",
                "description": "Analyse data.",
            },
            "skills": [
                {
                    "name": "Skill",
                    "slug": "skill",
                    "version": "0.1.0",
                    "content": "Use careful recommendations.",
                }
            ],
            "memory": [
                {"tenant_id": "tenant-1", "title": "Partner", "body": "Partner memory"},
                {"tenant_id": None, "title": "Global", "body": "Global memory"},
            ],
            "permissions": ["request_approval"],
            "task": {
                "title": "Review account",
                "input": {"channel": "google_ads"},
            },
            "context": {"channel": "google_ads"},
        }

        system_prompt, user_prompt = build_prompts(execution_package)

        self.assertIn("Partner memory", system_prompt)
        self.assertIn("Global memory", system_prompt)
        self.assertIn("not guaranteed truth", system_prompt)
        self.assertIn("external changes require approval", system_prompt)
        self.assertIn("learning_candidates", system_prompt)
        self.assertIn("Review account", user_prompt)

    def test_json_output_normalisation(self):
        output = normalize_llm_output(
            '{"summary":"Done","findings":"one","recommendations":["two"],'
            '"learning_candidates":{"title":"T","body":"B"},"approval_required":true}'
        )

        self.assertEqual(output["summary"], "Done")
        self.assertEqual(output["findings"], ["one"])
        self.assertEqual(output["recommendations"], ["two"])
        self.assertEqual(output["learning_candidates"], [{"title": "T", "body": "B"}])
        self.assertTrue(output["approval_required"])

    def test_invalid_json_does_not_crash(self):
        output = normalize_llm_output("plain text")

        self.assertEqual(output["summary"], "plain text")
        self.assertEqual(output["findings"], [])
        self.assertEqual(output["recommendations"], [])
        self.assertEqual(output["learning_candidates"], [])
        self.assertTrue(output["approval_required"])


if __name__ == "__main__":
    unittest.main()
