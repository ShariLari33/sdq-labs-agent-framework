from __future__ import annotations

import json
import os
import sys
import time

from packages.paperclip.client import PaperclipClient, PaperclipClientError


COMPANY_NAME = "SDQ Labs Growth Sandbox"
TASK_TITLE = "Analyse baseline Google Ads performance"
TENANT_SLUG = "sdq-labs-growth-sandbox"


def task_instructions() -> str:
    return "\n".join(
        [
            "Use SDQ Google Ads performance summary for tenant slug sdq-labs-growth-sandbox.",
            "Report findings and recommendations for the baseline synthetic Google Ads period.",
            "Campaigns: Brand Search, AI Automation Non Brand, Broad Growth Experiments.",
            "No external changes without approval.",
            "Approval is required before any action outside Paperclip.",
        ]
    )


def bootstrap() -> int:
    client = PaperclipClient()
    if not client.health():
        print(json.dumps({"status": "skipped", "reason": "paperclip_unavailable"}))
        return 0
    if not client.has_token():
        print(json.dumps({"status": "skipped", "reason": "missing_operator_token"}))
        return 0

    try:
        client.verify_operator()
        company = client.get_or_create_company(
            COMPANY_NAME,
            "Synthetic SDQ Labs sandbox company for local end-to-end demos.",
        )
        company_id = company["id"]
        agent = client.get_or_create_hermes_gateway_agent(company_id)
        if not agent:
            print(json.dumps({"status": "skipped", "reason": "hermes_gateway_agent_not_found_or_gateway_key_missing", "company_id": company_id}))
            return 0
        agent_id = agent["id"]
        task = client.get_or_create_task(company_id, TASK_TITLE, task_instructions(), agent_id)
        task_id = task["id"]
        if task.get("assigneeAgentId") != agent_id:
            task = client.assign_task(task_id, agent_id)
        try:
            client.wake_agent(agent_id, task_id)
        except PaperclipClientError:
            pass
    except PaperclipClientError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps({"status": "passed", "company_id": company_id, "agent_id": agent_id, "task_id": task_id}))
    return 0


def verify(timeout_seconds: int = 60) -> int:
    client = PaperclipClient()
    if not client.health():
        print(json.dumps({"status": "skipped", "reason": "paperclip_unavailable"}))
        return 0
    if not client.has_token():
        print(json.dumps({"status": "skipped", "reason": "missing_operator_token"}))
        return 0

    try:
        company = client.find_company(COMPANY_NAME)
        if not company:
            raise PaperclipClientError("sandbox company not found")
        company_id = company["id"]
        agent = client.find_registered_hermes_gateway_agent(company_id)
        if not agent:
            raise PaperclipClientError("Hermes Gateway agent not found")
        agent_id = agent["id"]
        task = client.find_task(company_id, TASK_TITLE)
        if not task:
            raise PaperclipClientError("sandbox task not found")
        task_id = task["id"]
        if task.get("assigneeAgentId") not in {agent_id, None}:
            raise PaperclipClientError("sandbox task assigned to unexpected agent")

        deadline = time.time() + timeout_seconds
        observed_update = False
        while time.time() < deadline:
            current = client.get_task(task_id)
            comments = client.task_comments(task_id)
            observed_update = bool(comments) or current.get("status") in {"in_progress", "needs_review", "done", "completed"}
            if observed_update:
                break
            time.sleep(3)
    except PaperclipClientError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "company_id": company_id,
                "agent_id": agent_id,
                "task_id": task_id,
                "task_update_observed": observed_update,
                "approval_required": True,
                "sdq_tenant_slug": TENANT_SLUG,
            }
        )
    )
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "bootstrap"
    if command == "bootstrap":
        raise SystemExit(bootstrap())
    if command == "verify":
        raise SystemExit(verify())
    raise SystemExit(f"Unknown command: {command}")
