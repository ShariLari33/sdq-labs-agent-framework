from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class PaperclipClientError(RuntimeError):
    pass


class PaperclipClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.getenv("PAPERCLIP_API_BASE_URL") or "http://localhost:3100/api").rstrip("/")
        self.token = token if token is not None else os.getenv("PAPERCLIP_OPERATOR_API_TOKEN", "")

    def has_token(self) -> bool:
        return bool(self.token and self.token.strip())

    def health(self) -> bool:
        url = self.base_url.removesuffix("/api") + "/health"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

    def verify_operator(self) -> dict:
        try:
            return self.request("GET", "/auth/profile")
        except PaperclipClientError:
            return {"ok": True, "fallback": "auth-profile-unavailable"}

    def list_companies(self) -> list[dict]:
        return self.request("GET", "/companies")

    def find_company(self, name: str) -> dict | None:
        for company in self.list_companies():
            if company.get("name") == name:
                return company
        return None

    def create_company(self, name: str, description: str | None = None) -> dict:
        payload = {"name": name, "description": description or ""}
        return self.request("POST", "/companies", payload)

    def get_or_create_company(self, name: str, description: str | None = None) -> dict:
        return self.find_company(name) or self.create_company(name, description)

    def list_agents(self, company_id: str) -> list[dict]:
        return self.request("GET", f"/companies/{company_id}/agents")

    def find_registered_hermes_gateway_agent(self, company_id: str) -> dict | None:
        candidates = []
        for agent in self.list_agents(company_id):
            adapter_type = agent.get("adapterType") or agent.get("adapter_type")
            name = agent.get("name") or agent.get("agentName") or ""
            if adapter_type == "hermes_gateway" or "Hermes Gateway" in name:
                candidates.append(agent)
        return candidates[0] if candidates else None

    def create_hermes_gateway_agent(
        self,
        company_id: str,
        api_base_url: str,
        api_key: str,
        paperclip_api_url: str,
    ) -> dict:
        payload = {
            "name": "Hermes Gateway Google Ads Runtime",
            "role": "general",
            "title": "Google Ads Performance Analyst",
            "capabilities": "Hermes gateway runtime for SDQ Labs Growth Sandbox Google Ads analysis.",
            "adapterType": "hermes_gateway",
            "adapterConfig": {
                "apiBaseUrl": api_base_url,
                "apiKey": api_key,
                "paperclipApiUrl": paperclip_api_url,
                "sessionKeyStrategy": "issue",
                "timeoutSec": 1800,
                "eventReconnectMs": 2000,
                "dangerouslyAllowInsecureRemoteHttp": True,
            },
            "permissions": {
                "canAssignTasks": True,
                "canCreateSkills": True,
            },
            "metadata": {"source": "sdq-sandbox-bootstrap"},
        }
        return self.request("POST", f"/companies/{company_id}/agents", payload)

    def get_or_create_hermes_gateway_agent(self, company_id: str) -> dict | None:
        existing = self.find_registered_hermes_gateway_agent(company_id)
        if existing:
            return existing

        api_base_url = os.getenv("HERMES_GATEWAY_API_BASE_URL", "http://hermes-gateway:8642")
        paperclip_api_url = os.getenv("HERMES_PAPERCLIP_API_URL", "http://server:3100/api")
        api_key = os.getenv("HERMES_GATEWAY_API_KEY") or os.getenv("API_SERVER_KEY")
        if not api_key:
            return None
        return self.create_hermes_gateway_agent(company_id, api_base_url, api_key, paperclip_api_url)

    def list_tasks(self, company_id: str, assignee_agent_id: str | None = None) -> list[dict]:
        query = ""
        if assignee_agent_id:
            query = "?" + urllib.parse.urlencode({"assigneeAgentId": assignee_agent_id})
        response = self.request("GET", f"/companies/{company_id}/issues{query}")
        if isinstance(response, list):
            return response
        return response.get("issues") or response.get("items") or []

    def find_task(self, company_id: str, title: str) -> dict | None:
        for task in self.list_tasks(company_id):
            if task.get("title") == title:
                return task
        return None

    def create_task(self, company_id: str, title: str, instructions: str, agent_id: str) -> dict:
        payload = {
            "title": title,
            "description": instructions,
            "assigneeAgentId": agent_id,
            "status": "todo",
            "priority": "medium",
            "workMode": "standard",
        }
        return self.request("POST", f"/companies/{company_id}/issues", payload)

    def get_or_create_task(self, company_id: str, title: str, instructions: str, agent_id: str) -> dict:
        task = self.find_task(company_id, title)
        if task:
            return task
        return self.create_task(company_id, title, instructions, agent_id)

    def assign_task(self, task_id: str, agent_id: str) -> dict:
        return self.request("PATCH", f"/issues/{task_id}", {"assigneeAgentId": agent_id})

    def get_task(self, task_id: str) -> dict:
        return self.request("GET", f"/issues/{task_id}")

    def task_comments(self, task_id: str) -> list[dict]:
        response = self.request("GET", f"/issues/{task_id}/comments")
        if isinstance(response, list):
            return response
        return response.get("comments") or response.get("items") or []

    def wake_agent(self, agent_id: str, issue_id: str) -> dict:
        return self.request(
            "POST",
            f"/agents/{agent_id}/wakeup",
            {"source": "sandbox", "payload": {"issueId": issue_id}},
        )

    def request(self, method: str, path: str, payload: dict | None = None) -> dict | list:
        if not self.has_token():
            raise PaperclipClientError("Paperclip operator token is not configured")

        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PaperclipClientError(
                f"Paperclip API request failed: {method} {path} HTTP {exc.code}: {redact(detail, self.token)}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PaperclipClientError(f"Paperclip API unavailable: {exc.reason}") from exc


def redact(value: str, token: str | None) -> str:
    if token:
        value = value.replace(token, "[redacted]")
    return value
