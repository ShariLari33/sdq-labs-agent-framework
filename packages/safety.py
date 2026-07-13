from __future__ import annotations

import os


SANDBOX_TENANT_SLUG = "sdq-labs-growth-sandbox"


class SafetyError(RuntimeError):
    pass


def env_bool(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def sdq_environment() -> str:
    value = os.getenv("SDQ_ENVIRONMENT", "development").strip().lower()
    if value not in {"sandbox", "development", "production"}:
        raise SafetyError("SDQ_ENVIRONMENT must be sandbox, development, or production")
    return value


def allow_auto_approvals() -> bool:
    return env_bool("SDQ_ALLOW_AUTO_APPROVALS")


def allow_auto_evolution() -> bool:
    return env_bool("SDQ_ALLOW_AUTO_EVOLUTION")


def allow_synthetic_data() -> bool:
    return env_bool("SDQ_ALLOW_SYNTHETIC_DATA")


def assert_safe_startup() -> None:
    if sdq_environment() == "production" and (
        allow_auto_approvals() or allow_auto_evolution() or allow_synthetic_data()
    ):
        raise SafetyError(
            "production refuses auto approvals, auto evolution, and synthetic data"
        )


def assert_sandbox_tenant(tenant_slug: str) -> None:
    if tenant_slug != SANDBOX_TENANT_SLUG:
        raise SafetyError("automatic sandbox actions are only allowed for the sandbox tenant")


def assert_synthetic_data_allowed(tenant_slug: str) -> None:
    assert_safe_startup()
    assert_sandbox_tenant(tenant_slug)
    if sdq_environment() != "sandbox" or not allow_synthetic_data():
        raise SafetyError("synthetic data import requires sandbox mode and SDQ_ALLOW_SYNTHETIC_DATA=true")


def assert_auto_approval_allowed(tenant_slug: str) -> None:
    assert_safe_startup()
    assert_sandbox_tenant(tenant_slug)
    if sdq_environment() != "sandbox" or not allow_auto_approvals():
        raise SafetyError("automatic approval requires sandbox mode and SDQ_ALLOW_AUTO_APPROVALS=true")


def assert_auto_evolution_allowed(tenant_slug: str) -> None:
    assert_safe_startup()
    assert_sandbox_tenant(tenant_slug)
    if sdq_environment() != "sandbox" or not allow_auto_evolution():
        raise SafetyError("automatic evolution requires sandbox mode and SDQ_ALLOW_AUTO_EVOLUTION=true")
