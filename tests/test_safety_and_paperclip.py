import io
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from packages.paperclip.client import PaperclipClient, PaperclipClientError
from packages.safety import (
    SafetyError,
    assert_auto_approval_allowed,
    assert_auto_evolution_allowed,
    assert_safe_startup,
    assert_synthetic_data_allowed,
)


class SafetyBoundaryTests(unittest.TestCase):
    def test_production_refuses_unsafe_flags(self):
        with patch.dict(
            os.environ,
            {
                "SDQ_ENVIRONMENT": "production",
                "SDQ_ALLOW_AUTO_APPROVALS": "true",
                "SDQ_ALLOW_AUTO_EVOLUTION": "false",
                "SDQ_ALLOW_SYNTHETIC_DATA": "false",
            },
            clear=False,
        ):
            with self.assertRaises(SafetyError):
                assert_safe_startup()

    def test_sandbox_allows_controlled_automatic_approvals(self):
        with sandbox_env():
            assert_auto_approval_allowed("sdq-labs-growth-sandbox")

    def test_non_sandbox_tenant_cannot_auto_approve(self):
        with sandbox_env():
            with self.assertRaises(SafetyError):
                assert_auto_approval_allowed("demo-partner-a")

    def test_non_sandbox_tenant_cannot_auto_evolve(self):
        with sandbox_env():
            with self.assertRaises(SafetyError):
                assert_auto_evolution_allowed("demo-partner-a")

    def test_synthetic_import_requires_sandbox_flag(self):
        with patch.dict(
            os.environ,
            {
                "SDQ_ENVIRONMENT": "development",
                "SDQ_ALLOW_SYNTHETIC_DATA": "false",
            },
            clear=False,
        ):
            with self.assertRaises(SafetyError):
                assert_synthetic_data_allowed("sdq-labs-growth-sandbox")


class PaperclipClientTests(unittest.TestCase):
    def test_company_creation_is_idempotent(self):
        client = FakePaperclipClient()
        first = client.get_or_create_company("SDQ Labs Growth Sandbox")
        second = client.get_or_create_company("SDQ Labs Growth Sandbox")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(client.created_companies, 1)

    def test_task_creation_is_idempotent(self):
        client = FakePaperclipClient()
        company = client.get_or_create_company("SDQ Labs Growth Sandbox")
        first = client.get_or_create_task(company["id"], "Analyse baseline Google Ads performance", "body", "agent-1")
        second = client.get_or_create_task(company["id"], "Analyse baseline Google Ads performance", "body", "agent-1")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(client.created_tasks, 1)

    def test_missing_operator_token_skips_safely(self):
        client = PaperclipClient(token="")
        self.assertFalse(client.has_token())

    def test_invalid_token_fails_without_leaking_secret(self):
        token = "paperclip-secret-token"

        def raise_http_error(_request, timeout=15):
            raise HTTPError(
                url="http://localhost:3100/api/companies",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=io.BytesIO(f"bad token {token}".encode()),
            )

        with patch("urllib.request.urlopen", raise_http_error):
            client = PaperclipClient(token=token)
            with self.assertRaises(PaperclipClientError) as ctx:
                client.list_companies()

        self.assertNotIn(token, str(ctx.exception))
        self.assertIn("[redacted]", str(ctx.exception))

    def test_no_direct_paperclip_db_writes_in_client_or_scripts(self):
        paths = [
            "packages/paperclip/client.py",
            "packages/paperclip/sandbox_bootstrap.py",
            "sandbox/sdq-labs-growth/scripts/bootstrap-paperclip.sh",
            "sandbox/sdq-labs-growth/scripts/verify-paperclip-flow.sh",
        ]
        for path in paths:
            with self.subTest(path=path):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read().lower()
                self.assertNotIn("psql", text)
                self.assertNotIn("docker exec", text)
                self.assertNotIn("insert into", text)
                self.assertNotIn("update set", text)
                self.assertNotIn("update paperclip", text)
                self.assertNotIn("delete from", text)


class FakePaperclipClient(PaperclipClient):
    def __init__(self):
        super().__init__(token="fake")
        self.companies = []
        self.tasks = []
        self.created_companies = 0
        self.created_tasks = 0

    def list_companies(self):
        return self.companies

    def create_company(self, name, description=None):
        self.created_companies += 1
        company = {"id": f"company-{self.created_companies}", "name": name}
        self.companies.append(company)
        return company

    def list_tasks(self, company_id, assignee_agent_id=None):
        return [task for task in self.tasks if task["companyId"] == company_id]

    def create_task(self, company_id, title, instructions, agent_id):
        self.created_tasks += 1
        task = {
            "id": f"task-{self.created_tasks}",
            "companyId": company_id,
            "title": title,
            "description": instructions,
            "assigneeAgentId": agent_id,
        }
        self.tasks.append(task)
        return task


def sandbox_env():
    return patch.dict(
        os.environ,
        {
            "SDQ_ENVIRONMENT": "sandbox",
            "SDQ_ALLOW_AUTO_APPROVALS": "true",
            "SDQ_ALLOW_AUTO_EVOLUTION": "true",
            "SDQ_ALLOW_SYNTHETIC_DATA": "true",
        },
        clear=False,
    )


if __name__ == "__main__":
    unittest.main()
