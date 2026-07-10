import os
from datetime import datetime
import psycopg
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from packages.ai.contracts import LLMRequest
from packages.ai.gateway import LLMGateway
from packages.ai.providers.base import LLMProviderError
from packages.evolution.engine import analyse_candidate
from packages.evolution.proposal_builder import (
    ProposalBuilderConflictError,
    build_skill_proposal,
)
from packages.evolution.versioning import (
    build_repair_preview,
    get_latest_skill_version,
    next_minor_version,
    parse_semantic_version,
    ProposalNotFoundError,
    RejectedProposalError,
    skill_integrity_report,
    SkillVersionContentConflictError,
    TargetSkillNotFoundError,
    approve_proposal as approve_evolution_proposal,
    reject_proposal as reject_evolution_proposal,
    restore_skill_version as restore_skill_version_status,
)
from packages.execution.output_parser import normalize_llm_output
from packages.execution.prompt_builder import build_prompts
from packages.performance.analytics import NoPerformanceDataError, calculate_google_ads_summary
from packages.performance.contracts import PerformanceFilters
from packages.performance.csv_importer import (
    DuplicateImportError,
    import_google_ads_csv,
)
from packages.performance.normalizer import CsvValidationError
from packages.performance.repository import (
    get_google_ads_summary_data,
    get_import_by_id,
    get_imports_for_tenant,
)
from packages.tools.google_ads_performance_reader import read_google_ads_performance

app = FastAPI(title="SDQ Labs Agent Framework API")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents"
)

class TaskCreate(BaseModel):
    tenant_slug: str
    title: str
    input: dict = Field(default_factory=dict)


class SkillVersionCreate(BaseModel):
    version: str
    content: str
    status: str = "draft"


class ApprovalReview(BaseModel):
    reviewed_by: str
    comment: str


class MemoryCreate(BaseModel):
    memory_type: str
    title: str
    body: str
    source: str = "manual"
    confidence: str = "medium"
    metadata: dict = Field(default_factory=dict)


class ImprovementCandidateCreate(BaseModel):
    candidate_type: str
    title: str
    body: str
    metadata: dict = Field(default_factory=dict)


class ImprovementCandidateReview(BaseModel):
    reviewed_by: str
    review_comment: str


class ModelRouteUpdate(BaseModel):
    provider: str
    model_name: str


class PerformanceFeedbackCreate(BaseModel):
    task_id: str | None = None
    agent_run_id: str | None = None
    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    baseline_value: float | None = None
    metadata: dict = Field(default_factory=dict)


class CandidateEvidenceCreate(BaseModel):
    evidence_type: str
    source_id: str | None = None
    description: str | None = None
    weight: float = 1
    metadata: dict = Field(default_factory=dict)


class CandidateEvaluationCreate(BaseModel):
    evaluator_type: str
    score: float | None = None
    verdict: str
    rationale: str | None = None
    metadata: dict = Field(default_factory=dict)


class EvolutionProposalReview(BaseModel):
    reviewed_by: str
    comment: str


def get_db_connection():
    return psycopg.connect(DATABASE_URL)


def get_tenant_by_slug(tenant_slug):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, slug, created_at FROM tenants WHERE slug = %s",
                (tenant_slug,)
            )
            tenant = cur.fetchone()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "id": tenant[0],
        "name": tenant[1],
        "slug": tenant[2],
        "created_at": tenant[3],
    }


def emit_event(tenant_id, event_type, entity_type, entity_id, payload):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (tenant_id, event_type, entity_type, entity_id, payload)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    tenant_id,
                    event_type,
                    entity_type,
                    entity_id,
                    psycopg.types.json.Jsonb(payload),
                )
            )
            event = cur.fetchone()
            conn.commit()

    return {"id": event[0], "created_at": event[1]}


def get_default_agent_template():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, version, created_at
                FROM agent_templates
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            template = cur.fetchone()

    if not template:
        raise HTTPException(status_code=500, detail="No agent template available")

    return {
        "id": template[0],
        "name": template[1],
        "description": template[2],
        "version": template[3],
        "created_at": template[4],
    }


def resolve_approved_skills_for_agent(agent_template_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.slug,
                    sv.version,
                    sv.content,
                    sv.id
                FROM agent_template_skills ats
                JOIN skills s ON s.id = ats.skill_id
                JOIN LATERAL (
                    SELECT id, version, content
                    FROM skill_versions
                    WHERE skill_id = s.id AND status = 'approved'
                    ORDER BY created_at DESC
                    LIMIT 1
                ) sv ON true
                WHERE ats.agent_template_id = %s
                ORDER BY s.name ASC
                """,
                (agent_template_id,)
            )
            rows = cur.fetchall()

    return [
        {
            "skill_id": str(row[0]),
            "name": row[1],
            "slug": row[2],
            "version": row[3],
            "content": row[4],
            "skill_version_id": str(row[5]),
        }
        for row in rows
    ]


def get_memory_for_tenant(tenant_id, memory_type=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            params = [tenant_id]
            memory_type_filter = ""

            if memory_type:
                memory_type_filter = "AND memory_type = %s"
                params.append(memory_type)

            cur.execute(
                f"""
                SELECT
                    id,
                    tenant_id,
                    memory_type,
                    title,
                    body,
                    source,
                    status,
                    confidence,
                    metadata,
                    created_at
                FROM memory_items
                WHERE (tenant_id = %s OR tenant_id IS NULL)
                  AND status = 'active'
                  {memory_type_filter}
                ORDER BY created_at DESC
                """,
                tuple(params)
            )
            rows = cur.fetchall()

    return [serialize_memory_item(row) for row in rows]


def resolve_capability_for_task(task_input):
    channel = task_input.get("channel")
    slug = "performance_analysis"

    if channel == "google_ads":
        slug = "performance_analysis"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    slug,
                    name,
                    description,
                    default_model_tier,
                    approval_required,
                    created_at
                FROM capabilities
                WHERE slug = %s
                """,
                (slug,)
            )
            capability = cur.fetchone()

    if not capability:
        raise HTTPException(status_code=500, detail="Capability not found")

    return serialize_capability(capability)


def resolve_worker_for_capability(capability_id, channel):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    w.id,
                    w.name,
                    w.worker_type,
                    w.endpoint,
                    w.status,
                    cw.channel,
                    cw.priority
                FROM capability_workers cw
                JOIN worker_registry w ON w.id = cw.worker_id
                WHERE cw.capability_id = %s
                  AND cw.status = 'active'
                  AND w.status = 'active'
                  AND (cw.channel = %s OR cw.channel IS NULL)
                ORDER BY cw.priority ASC, cw.created_at ASC
                LIMIT 1
                """,
                (capability_id, channel)
            )
            worker = cur.fetchone()

    if not worker:
        raise HTTPException(status_code=500, detail="No active worker for capability")

    return {
        "id": str(worker[0]),
        "name": worker[1],
        "worker_type": worker[2],
        "endpoint": worker[3],
        "status": worker[4],
        "channel": worker[5],
        "priority": worker[6],
    }


def resolve_model_route(
    task_type,
    sensitivity="internal",
    cost_tier="low",
    quality_tier="standard"
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    task_type,
                    sensitivity,
                    cost_tier,
                    quality_tier,
                    provider,
                    model_name,
                    status,
                    created_at
                FROM model_routes
                WHERE task_type = %s
                  AND sensitivity = %s
                  AND cost_tier = %s
                  AND quality_tier = %s
                  AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (task_type, sensitivity, cost_tier, quality_tier)
            )
            route = cur.fetchone()

    if not route:
        return {
            "id": None,
            "task_type": task_type,
            "sensitivity": sensitivity,
            "cost_tier": cost_tier,
            "quality_tier": quality_tier,
            "provider": "mock",
            "model_name": "mock-model-v0",
            "status": "fallback",
        }

    return serialize_model_route(route)


def resolve_approved_skills_for_capability(capability_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.slug,
                    sv.version,
                    sv.content,
                    sv.id
                FROM capability_skills cs
                JOIN skills s ON s.id = cs.skill_id
                JOIN LATERAL (
                    SELECT id, version, content
                    FROM skill_versions
                    WHERE skill_id = s.id AND status = 'approved'
                    ORDER BY created_at DESC
                    LIMIT 1
                ) sv ON true
                WHERE cs.capability_id = %s
                ORDER BY s.name ASC
                """,
                (capability_id,)
            )
            rows = cur.fetchall()

    return [
        {
            "skill_id": str(row[0]),
            "name": row[1],
            "slug": row[2],
            "version": row[3],
            "content": row[4],
            "skill_version_id": str(row[5]),
        }
        for row in rows
    ]


def plan_execution(task, tenant):
    capability = resolve_capability_for_task(task["input"])
    channel = task["input"].get("channel")
    worker = resolve_worker_for_capability(capability["id"], channel)
    skills = resolve_approved_skills_for_capability(capability["id"])
    memory = get_memory_for_tenant(tenant["id"])
    model = resolve_model_route(capability["slug"])
    permissions = [
        "read_performance_data",
        "create_recommendations",
        "create_learning_candidate",
        "request_approval",
    ]
    tools = []
    if channel == "google_ads" and capability["slug"] == "performance_analysis":
        tools.append(
            {
                "name": "google_ads_performance_reader",
                "filters": {
                    "date_from": task["input"].get("date_from"),
                    "date_to": task["input"].get("date_to"),
                    "campaign_id": task["input"].get("campaign_id"),
                    "campaign_status": task["input"].get("campaign_status"),
                },
            }
        )

    return {
        "task": task,
        "tenant": {
            "id": str(tenant["id"]),
            "name": tenant["name"],
            "slug": tenant["slug"],
        },
        "capability": capability,
        "worker": worker,
        "model": model,
        "skills": skills,
        "memory": memory,
        "permissions": permissions,
        "tools": tools,
        "context": {
            "channel": channel,
            "approval_required": capability["approval_required"],
        },
    }


def execute_execution_tools(execution_package, tenant, task_id):
    for tool in execution_package["tools"]:
        if tool.get("name") != "google_ads_performance_reader":
            continue

        emit_event(
            tenant["id"],
            "ToolExecutionStarted",
            "task",
            task_id,
            {"tool": tool["name"], "filters": tool.get("filters", {})},
        )
        try:
            with get_db_connection() as conn:
                summary = read_google_ads_performance(
                    conn,
                    tenant["id"],
                    tool.get("filters", {}),
                )
        except NoPerformanceDataError as exc:
            emit_event(
                tenant["id"],
                "ToolExecutionFailed",
                "task",
                task_id,
                {"tool": tool["name"], "error": str(exc)},
            )
            raise HTTPException(status_code=400, detail=str(exc))

        execution_package["context"]["performance_summary"] = summary
        emit_event(
            tenant["id"],
            "ToolExecutionCompleted",
            "task",
            task_id,
            {
                "tool": tool["name"],
                "import_ids": summary["data_quality"]["import_ids"],
                "date_from": summary["period"]["date_from"],
                "date_to": summary["period"]["date_to"],
            },
        )

    return execution_package


def serialize_task(row):
    return {
        "id": str(row[0]),
        "title": row[1],
        "status": row[2],
        "input": row[3],
        "created_at": row[4].isoformat()
    }


def serialize_agent_run(row):
    return {
        "id": str(row[0]),
        "task_id": str(row[1]) if row[1] else None,
        "agent_template_id": str(row[2]) if row[2] else None,
        "status": row[3],
        "input": row[4],
        "output": row[5],
        "logs": row[6],
        "created_at": row[7].isoformat()
    }


def serialize_event(row):
    return {
        "id": str(row[0]),
        "event_type": row[1],
        "entity_type": row[2],
        "entity_id": str(row[3]) if row[3] else None,
        "payload": row[4],
        "created_at": row[5].isoformat()
    }


def serialize_learning(row):
    return {
        "id": str(row[0]),
        "scope": row[1],
        "title": row[2],
        "body": row[3],
        "confidence": row[4],
        "created_at": row[5].isoformat()
    }


def serialize_approval(row):
    return {
        "id": str(row[0]),
        "task_id": str(row[1]),
        "status": row[2],
        "requested_by": row[3],
        "created_at": row[4].isoformat()
    }


def serialize_approval_detail(row):
    return {
        "id": str(row[0]),
        "task_id": str(row[1]),
        "task_title": row[2],
        "status": row[3],
        "requested_by": row[4],
        "reviewed_by": row[5],
        "comment": row[6],
        "created_at": row[7].isoformat(),
        "reviewed_at": row[8].isoformat() if row[8] else None,
    }


def serialize_skill_version(row):
    return {
        "id": str(row[0]),
        "skill_id": str(row[1]),
        "version": row[2],
        "status": row[3],
        "content": row[4],
        "created_at": row[5].isoformat()
    }


def serialize_latest_skill_version(row):
    if not row[4]:
        return None

    return {
        "id": str(row[4]),
        "version": row[5],
        "status": row[6],
        "content": row[7],
        "created_at": row[8].isoformat()
    }


def serialize_memory_item(row):
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]) if row[1] else None,
        "memory_type": row[2],
        "title": row[3],
        "body": row[4],
        "source": row[5],
        "status": row[6],
        "confidence": row[7],
        "metadata": row[8],
        "created_at": row[9].isoformat(),
    }


def serialize_improvement_candidate(row):
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]) if row[1] else None,
        "candidate_type": row[2],
        "title": row[3],
        "body": row[4],
        "source_task_id": str(row[5]) if row[5] else None,
        "source_agent_run_id": str(row[6]) if row[6] else None,
        "status": row[7],
        "reviewed_by": row[8],
        "review_comment": row[9],
        "metadata": row[10],
        "created_at": row[11].isoformat(),
        "reviewed_at": row[12].isoformat() if row[12] else None,
    }


def serialize_capability(row):
    return {
        "id": str(row[0]),
        "slug": row[1],
        "name": row[2],
        "description": row[3],
        "default_model_tier": row[4],
        "approval_required": row[5],
        "created_at": row[6].isoformat(),
    }


def serialize_model_route(row):
    return {
        "id": str(row[0]),
        "task_type": row[1],
        "sensitivity": row[2],
        "cost_tier": row[3],
        "quality_tier": row[4],
        "provider": row[5],
        "model_name": row[6],
        "status": row[7],
        "created_at": row[8].isoformat(),
    }


def serialize_performance_feedback(row):
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "task_id": str(row[2]) if row[2] else None,
        "agent_run_id": str(row[3]) if row[3] else None,
        "metric_name": row[4],
        "metric_value": float(row[5]) if row[5] is not None else None,
        "metric_unit": row[6],
        "period_start": row[7].isoformat() if row[7] else None,
        "period_end": row[8].isoformat() if row[8] else None,
        "baseline_value": float(row[9]) if row[9] is not None else None,
        "metadata": row[10],
        "created_at": row[11].isoformat(),
    }


def serialize_candidate_evidence(row):
    return {
        "id": str(row[0]),
        "improvement_candidate_id": str(row[1]),
        "evidence_type": row[2],
        "source_id": str(row[3]) if row[3] else None,
        "description": row[4],
        "weight": float(row[5]),
        "metadata": row[6],
        "created_at": row[7].isoformat(),
    }


def serialize_candidate_evaluation(row):
    return {
        "id": str(row[0]),
        "improvement_candidate_id": str(row[1]),
        "evaluator_type": row[2],
        "score": float(row[3]) if row[3] is not None else None,
        "verdict": row[4],
        "rationale": row[5],
        "metadata": row[6],
        "created_at": row[7].isoformat(),
    }


def serialize_evolution_proposal(row):
    return {
        "id": str(row[0]),
        "improvement_candidate_id": str(row[1]),
        "proposal_type": row[2],
        "target_skill_id": str(row[3]) if row[3] else None,
        "base_skill_version_id": str(row[4]) if row[4] else None,
        "proposed_version": row[5],
        "proposed_content": row[6],
        "status": row[7],
        "created_by": row[8],
        "approved_by": row[9],
        "approval_comment": row[10],
        "created_at": row[11].isoformat(),
        "approved_at": row[12].isoformat() if row[12] else None,
    }


def get_candidate_context(candidate_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, candidate_type, status, source_agent_run_id
                FROM improvement_candidates
                WHERE id = %s
                """,
                (candidate_id,)
            )
            candidate = cur.fetchone()

    if not candidate:
        raise HTTPException(status_code=404, detail="Improvement candidate not found")

    return {
        "id": candidate[0],
        "tenant_id": candidate[1],
        "candidate_type": candidate[2],
        "status": candidate[3],
        "source_agent_run_id": candidate[4],
    }


def llm_usage_payload(result):
    return {
        "provider": result.provider,
        "model": result.model,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "total_tokens": result.usage.total_tokens,
        "latency_ms": result.latency_ms,
        "provider_response_id": result.provider_response_id,
    }


def first_learning_candidate(output, task_title):
    candidates = output.get("learning_candidates") or []
    if candidates:
        candidate = candidates[0]
        if isinstance(candidate, dict):
            return {
                "title": candidate.get("title") or f"Learning from {task_title}",
                "body": candidate.get("body") or str(candidate),
            }
        return {
            "title": f"Learning from {task_title}",
            "body": str(candidate),
        }

    return {
        "title": f"Learning from {task_title}",
        "body": "No learning candidate was returned by the provider.",
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "sdq-agent-framework-api"}


@app.get("/llm-providers/health")
def llm_provider_health():
    return LLMGateway().health()

@app.get("/tenants")
def get_tenants():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, created_at FROM tenants ORDER BY created_at ASC")
            rows = cur.fetchall()

    return {
        "tenants": [
            {
                "id": str(row[0]),
                "name": row[1],
                "slug": row[2],
                "created_at": row[3].isoformat()
            }
            for row in rows
        ]
    }


@app.get("/capabilities")
def list_capabilities():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    slug,
                    name,
                    description,
                    default_model_tier,
                    approval_required,
                    created_at
                FROM capabilities
                ORDER BY created_at ASC
                """
            )
            capability_rows = cur.fetchall()

            capabilities = []
            for capability in capability_rows:
                cur.execute(
                    """
                    SELECT
                        w.id,
                        w.name,
                        w.worker_type,
                        w.endpoint,
                        w.status,
                        cw.channel,
                        cw.priority
                    FROM capability_workers cw
                    JOIN worker_registry w ON w.id = cw.worker_id
                    WHERE cw.capability_id = %s
                    ORDER BY cw.priority ASC, cw.created_at ASC
                    """,
                    (capability[0],)
                )
                worker_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.name,
                        s.slug,
                        sv.version,
                        sv.content,
                        sv.id
                    FROM capability_skills cs
                    JOIN skills s ON s.id = cs.skill_id
                    LEFT JOIN LATERAL (
                        SELECT id, version, content
                        FROM skill_versions
                        WHERE skill_id = s.id AND status = 'approved'
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) sv ON true
                    WHERE cs.capability_id = %s
                    ORDER BY s.name ASC
                    """,
                    (capability[0],)
                )
                skill_rows = cur.fetchall()

                capability_data = serialize_capability(capability)
                capability_data["workers"] = [
                    {
                        "id": str(worker[0]),
                        "name": worker[1],
                        "worker_type": worker[2],
                        "endpoint": worker[3],
                        "status": worker[4],
                        "channel": worker[5],
                        "priority": worker[6],
                    }
                    for worker in worker_rows
                ]
                capability_data["skills"] = [
                    {
                        "skill_id": str(skill[0]),
                        "name": skill[1],
                        "slug": skill[2],
                        "version": skill[3],
                        "content": skill[4],
                        "skill_version_id": str(skill[5]) if skill[5] else None,
                    }
                    for skill in skill_rows
                ]
                capabilities.append(capability_data)

    return {"capabilities": capabilities}


@app.post("/model-routes/{route_id}/activate-provider")
def activate_model_route_provider(route_id: str, payload: ModelRouteUpdate):
    if not payload.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name is required")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE model_routes
                SET provider = %s, model_name = %s
                WHERE id = %s
                RETURNING
                    id,
                    task_type,
                    sensitivity,
                    cost_tier,
                    quality_tier,
                    provider,
                    model_name,
                    status,
                    created_at
                """,
                (payload.provider, payload.model_name, route_id)
            )
            route = cur.fetchone()
            conn.commit()

    if not route:
        raise HTTPException(status_code=404, detail="Model route not found")

    route_data = serialize_model_route(route)
    emit_event(
        None,
        "ModelRouteUpdated",
        "model_route",
        route[0],
        {
            "provider": payload.provider,
            "model_name": payload.model_name,
        }
    )

    return {"model_route": route_data}


@app.get("/execution-plan/preview/{tenant_slug}/{task_id}")
def preview_execution_plan(tenant_slug: str, task_id: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, input, created_at
                FROM tasks
                WHERE id = %s AND tenant_id = %s
                """,
                (task_id, tenant["id"])
            )
            task = cur.fetchone()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"execution_plan": plan_execution(serialize_task(task), tenant)}


@app.get("/skills")
def list_skills():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.slug,
                    s.description,
                    sv.id,
                    sv.version,
                    sv.status,
                    sv.content,
                    sv.created_at,
                    s.status,
                    s.created_at
                FROM skills s
                LEFT JOIN LATERAL (
                    SELECT id, version, status, content, created_at
                    FROM skill_versions
                    WHERE skill_id = s.id AND status = 'approved'
                    ORDER BY created_at DESC
                    LIMIT 1
                ) sv ON true
                ORDER BY s.name ASC
                """
            )
            rows = cur.fetchall()

    return {
        "skills": [
            {
                "id": str(row[0]),
                "name": row[1],
                "slug": row[2],
                "description": row[3],
                "status": row[9],
                "created_at": row[10].isoformat(),
                "latest_approved_version": serialize_latest_skill_version(row),
            }
            for row in rows
        ]
    }


@app.get("/agent-templates")
def list_agent_templates():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, version, created_at
                FROM agent_templates
                ORDER BY created_at ASC
                """
            )
            template_rows = cur.fetchall()

            templates = []
            for template in template_rows:
                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.name,
                        s.slug,
                        s.description,
                        sv.id,
                        sv.version,
                        sv.status,
                        sv.content,
                        sv.created_at,
                        s.status,
                        s.created_at
                    FROM agent_template_skills ats
                    JOIN skills s ON s.id = ats.skill_id
                    LEFT JOIN LATERAL (
                        SELECT id, version, status, content, created_at
                        FROM skill_versions
                        WHERE skill_id = s.id AND status = 'approved'
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) sv ON true
                    WHERE ats.agent_template_id = %s
                    ORDER BY s.name ASC
                    """,
                    (template[0],)
                )
                skill_rows = cur.fetchall()

                templates.append(
                    {
                        "id": str(template[0]),
                        "name": template[1],
                        "description": template[2],
                        "version": template[3],
                        "created_at": template[4].isoformat(),
                        "skills": [
                            {
                                "id": str(skill[0]),
                                "name": skill[1],
                                "slug": skill[2],
                                "description": skill[3],
                                "status": skill[9],
                                "created_at": skill[10].isoformat(),
                                "latest_approved_version": serialize_latest_skill_version(skill),
                            }
                            for skill in skill_rows
                        ],
                    }
                )

    return {"agent_templates": templates}


@app.get("/approvals/{tenant_slug}")
def list_approvals(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.task_id,
                    t.title,
                    a.status,
                    a.requested_by,
                    a.reviewed_by,
                    a.comment,
                    a.created_at,
                    a.reviewed_at
                FROM approvals a
                JOIN tasks t ON t.id = a.task_id
                WHERE a.tenant_id = %s AND t.tenant_id = %s
                ORDER BY a.created_at DESC
                """,
                (tenant["id"], tenant["id"])
            )
            rows = cur.fetchall()

    return {"approvals": [serialize_approval_detail(row) for row in rows]}


def review_approval(approval_id, payload, approval_status, task_status):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.tenant_id, a.task_id, t.title
                FROM approvals a
                JOIN tasks t ON t.id = a.task_id
                WHERE a.id = %s AND t.tenant_id = a.tenant_id
                FOR UPDATE
                """,
                (approval_id,)
            )
            approval = cur.fetchone()

            if not approval:
                raise HTTPException(status_code=404, detail="Approval not found")

            cur.execute(
                """
                UPDATE approvals a
                SET status = %s,
                    reviewed_by = %s,
                    comment = %s,
                    reviewed_at = NOW()
                FROM tasks t
                WHERE a.id = %s
                  AND a.tenant_id = %s
                  AND t.id = a.task_id
                  AND t.tenant_id = a.tenant_id
                RETURNING
                    a.id,
                    a.task_id,
                    t.title,
                    a.status,
                    a.requested_by,
                    a.reviewed_by,
                    a.comment,
                    a.created_at,
                    a.reviewed_at
                """,
                (
                    approval_status,
                    payload.reviewed_by,
                    payload.comment,
                    approval[0],
                    approval[1],
                )
            )
            updated_approval = cur.fetchone()

            cur.execute(
                """
                UPDATE tasks
                SET status = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, title, status, input, created_at
                """,
                (task_status, approval[2], approval[1])
            )
            updated_task = cur.fetchone()

            conn.commit()

    return approval, updated_approval, updated_task


@app.post("/approvals/{approval_id}/approve")
def approve_approval(approval_id: str, payload: ApprovalReview):
    approval, updated_approval, updated_task = review_approval(
        approval_id,
        payload,
        "approved",
        "completed"
    )

    emit_event(
        approval[1],
        "ApprovalApproved",
        "approval",
        approval[0],
        {
            "task_id": str(approval[2]),
            "reviewed_by": payload.reviewed_by,
            "comment": payload.comment,
        }
    )
    emit_event(
        approval[1],
        "TaskCompleted",
        "task",
        approval[2],
        {"approval_id": str(approval[0])}
    )

    return {
        "approval": serialize_approval_detail(updated_approval),
        "task": serialize_task(updated_task),
    }


@app.post("/approvals/{approval_id}/reject")
def reject_approval(approval_id: str, payload: ApprovalReview):
    approval, updated_approval, updated_task = review_approval(
        approval_id,
        payload,
        "rejected",
        "revision_requested"
    )

    emit_event(
        approval[1],
        "ApprovalRejected",
        "approval",
        approval[0],
        {
            "task_id": str(approval[2]),
            "reviewed_by": payload.reviewed_by,
            "comment": payload.comment,
        }
    )
    emit_event(
        approval[1],
        "TaskRevisionRequested",
        "task",
        approval[2],
        {"approval_id": str(approval[0])}
    )

    return {
        "approval": serialize_approval_detail(updated_approval),
        "task": serialize_task(updated_task),
    }


@app.post("/memory/global")
def create_global_memory(payload: MemoryCreate):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_items (
                    tenant_id,
                    memory_type,
                    title,
                    body,
                    source,
                    confidence,
                    metadata
                )
                VALUES (NULL, %s, %s, %s, %s, %s, %s)
                RETURNING id, tenant_id, memory_type, title, body, source, status, confidence, metadata, created_at
                """,
                (
                    payload.memory_type,
                    payload.title,
                    payload.body,
                    payload.source,
                    payload.confidence,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            memory_item = cur.fetchone()
            conn.commit()

    emit_event(
        None,
        "GlobalMemoryItemCreated",
        "memory_item",
        memory_item[0],
        {"memory_type": payload.memory_type, "title": payload.title}
    )

    return {"memory_item": serialize_memory_item(memory_item)}


@app.get("/memory/{tenant_slug}")
def list_memory(tenant_slug: str, memory_type: str = None):
    tenant = get_tenant_by_slug(tenant_slug)
    return {"memory_items": get_memory_for_tenant(tenant["id"], memory_type)}


@app.post("/memory/{tenant_slug}")
def create_memory(tenant_slug: str, payload: MemoryCreate):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_items (
                    tenant_id,
                    memory_type,
                    title,
                    body,
                    source,
                    confidence,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, tenant_id, memory_type, title, body, source, status, confidence, metadata, created_at
                """,
                (
                    tenant["id"],
                    payload.memory_type,
                    payload.title,
                    payload.body,
                    payload.source,
                    payload.confidence,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            memory_item = cur.fetchone()
            conn.commit()

    emit_event(
        tenant["id"],
        "MemoryItemCreated",
        "memory_item",
        memory_item[0],
        {"memory_type": payload.memory_type, "title": payload.title}
    )

    return {"memory_item": serialize_memory_item(memory_item)}


@app.post("/improvement-candidates/global")
def create_global_improvement_candidate(payload: ImprovementCandidateCreate):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO improvement_candidates (
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    metadata
                )
                VALUES (NULL, %s, %s, %s, %s)
                RETURNING
                    id,
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    source_task_id,
                    source_agent_run_id,
                    status,
                    reviewed_by,
                    review_comment,
                    metadata,
                    created_at,
                    reviewed_at
                """,
                (
                    payload.candidate_type,
                    payload.title,
                    payload.body,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            candidate = cur.fetchone()
            conn.commit()

    emit_event(
        None,
        "GlobalImprovementCandidateCreated",
        "improvement_candidate",
        candidate[0],
        {"candidate_type": payload.candidate_type, "title": payload.title}
    )

    return {"improvement_candidate": serialize_improvement_candidate(candidate)}


@app.get("/improvement-candidates/{tenant_slug}")
def list_improvement_candidates(tenant_slug: str, candidate_type: str = None):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            params = [tenant["id"]]
            candidate_type_filter = ""

            if candidate_type:
                candidate_type_filter = "AND candidate_type = %s"
                params.append(candidate_type)

            cur.execute(
                f"""
                SELECT
                    id,
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    source_task_id,
                    source_agent_run_id,
                    status,
                    reviewed_by,
                    review_comment,
                    metadata,
                    created_at,
                    reviewed_at
                FROM improvement_candidates
                WHERE (tenant_id = %s OR tenant_id IS NULL)
                  {candidate_type_filter}
                ORDER BY created_at DESC
                """,
                tuple(params)
            )
            rows = cur.fetchall()

    return {
        "improvement_candidates": [
            serialize_improvement_candidate(row) for row in rows
        ]
    }


@app.post("/improvement-candidates/{tenant_slug}")
def create_improvement_candidate(tenant_slug: str, payload: ImprovementCandidateCreate):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO improvement_candidates (
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING
                    id,
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    source_task_id,
                    source_agent_run_id,
                    status,
                    reviewed_by,
                    review_comment,
                    metadata,
                    created_at,
                    reviewed_at
                """,
                (
                    tenant["id"],
                    payload.candidate_type,
                    payload.title,
                    payload.body,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            candidate = cur.fetchone()
            conn.commit()

    emit_event(
        tenant["id"],
        "ImprovementCandidateCreated",
        "improvement_candidate",
        candidate[0],
        {"candidate_type": payload.candidate_type, "title": payload.title}
    )

    return {"improvement_candidate": serialize_improvement_candidate(candidate)}


def review_improvement_candidate(candidate_id, payload, status):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE improvement_candidates
                SET status = %s,
                    reviewed_by = %s,
                    review_comment = %s,
                    reviewed_at = NOW()
                WHERE id = %s
                RETURNING
                    id,
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    source_task_id,
                    source_agent_run_id,
                    status,
                    reviewed_by,
                    review_comment,
                    metadata,
                    created_at,
                    reviewed_at
                """,
                (
                    status,
                    payload.reviewed_by,
                    payload.review_comment,
                    candidate_id,
                )
            )
            candidate = cur.fetchone()

            if not candidate:
                raise HTTPException(
                    status_code=404,
                    detail="Improvement candidate not found"
                )

            conn.commit()

    return candidate


@app.post("/improvement-candidates/{candidate_id}/approve")
def approve_improvement_candidate(
    candidate_id: str,
    payload: ImprovementCandidateReview
):
    candidate = review_improvement_candidate(candidate_id, payload, "approved")

    emit_event(
        candidate[1],
        "ImprovementCandidateApproved",
        "improvement_candidate",
        candidate[0],
        {
            "reviewed_by": payload.reviewed_by,
            "review_comment": payload.review_comment,
        }
    )

    return {"improvement_candidate": serialize_improvement_candidate(candidate)}


@app.post("/improvement-candidates/{candidate_id}/reject")
def reject_improvement_candidate(
    candidate_id: str,
    payload: ImprovementCandidateReview
):
    candidate = review_improvement_candidate(candidate_id, payload, "rejected")

    emit_event(
        candidate[1],
        "ImprovementCandidateRejected",
        "improvement_candidate",
        candidate[0],
        {
            "reviewed_by": payload.reviewed_by,
            "review_comment": payload.review_comment,
        }
    )

    return {"improvement_candidate": serialize_improvement_candidate(candidate)}


@app.post("/performance-feedback/{tenant_slug}")
def create_performance_feedback(
    tenant_slug: str,
    payload: PerformanceFeedbackCreate
):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO performance_feedback (
                    tenant_id,
                    task_id,
                    agent_run_id,
                    metric_name,
                    metric_value,
                    metric_unit,
                    period_start,
                    period_end,
                    baseline_value,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    tenant_id,
                    task_id,
                    agent_run_id,
                    metric_name,
                    metric_value,
                    metric_unit,
                    period_start,
                    period_end,
                    baseline_value,
                    metadata,
                    created_at
                """,
                (
                    tenant["id"],
                    payload.task_id,
                    payload.agent_run_id,
                    payload.metric_name,
                    payload.metric_value,
                    payload.metric_unit,
                    payload.period_start,
                    payload.period_end,
                    payload.baseline_value,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            feedback = cur.fetchone()
            linked_evidence = []

            if payload.agent_run_id:
                cur.execute(
                    """
                    SELECT id
                    FROM improvement_candidates
                    WHERE tenant_id = %s
                      AND source_agent_run_id = %s
                      AND status = 'proposed'
                    """,
                    (tenant["id"], payload.agent_run_id)
                )
                candidates = cur.fetchall()
                for candidate in candidates:
                    change_text = "no baseline"
                    if (
                        payload.metric_value is not None
                        and payload.baseline_value is not None
                    ):
                        change_text = str(payload.metric_value - payload.baseline_value)

                    cur.execute(
                        """
                        INSERT INTO candidate_evidence (
                            improvement_candidate_id,
                            evidence_type,
                            source_id,
                            description,
                            metadata
                        )
                        VALUES (%s, 'performance_metric', %s, %s, %s)
                        RETURNING
                            id,
                            improvement_candidate_id,
                            evidence_type,
                            source_id,
                            description,
                            weight,
                            metadata,
                            created_at
                        """,
                        (
                            candidate[0],
                            feedback[0],
                            (
                                f"{payload.metric_name}={payload.metric_value} "
                                f"{payload.metric_unit or ''}; change from baseline: {change_text}"
                            ),
                            psycopg.types.json.Jsonb(
                                {
                                    "metric_name": payload.metric_name,
                                    "metric_value": payload.metric_value,
                                    "metric_unit": payload.metric_unit,
                                    "baseline_value": payload.baseline_value,
                                    "period_start": payload.period_start.isoformat()
                                    if payload.period_start else None,
                                    "period_end": payload.period_end.isoformat()
                                    if payload.period_end else None,
                                }
                            ),
                        )
                    )
                    linked_evidence.append(cur.fetchone())

            conn.commit()

    emit_event(
        tenant["id"],
        "PerformanceFeedbackCreated",
        "performance_feedback",
        feedback[0],
        {"metric_name": payload.metric_name, "agent_run_id": payload.agent_run_id}
    )
    for evidence in linked_evidence:
        emit_event(
            tenant["id"],
            "CandidateEvidenceAdded",
            "candidate_evidence",
            evidence[0],
            {
                "improvement_candidate_id": str(evidence[1]),
                "evidence_type": evidence[2],
                "source_id": str(evidence[3]) if evidence[3] else None,
            }
        )

    return {
        "performance_feedback": serialize_performance_feedback(feedback),
        "linked_evidence": [
            serialize_candidate_evidence(evidence) for evidence in linked_evidence
        ],
    }


@app.get("/performance-feedback/{tenant_slug}")
def list_performance_feedback(
    tenant_slug: str,
    metric_name: str = None,
    task_id: str = None,
    agent_run_id: str = None
):
    tenant = get_tenant_by_slug(tenant_slug)
    filters = []
    params = [tenant["id"]]

    if metric_name:
        filters.append("metric_name = %s")
        params.append(metric_name)
    if task_id:
        filters.append("task_id = %s")
        params.append(task_id)
    if agent_run_id:
        filters.append("agent_run_id = %s")
        params.append(agent_run_id)

    where_filters = ""
    if filters:
        where_filters = "AND " + " AND ".join(filters)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    tenant_id,
                    task_id,
                    agent_run_id,
                    metric_name,
                    metric_value,
                    metric_unit,
                    period_start,
                    period_end,
                    baseline_value,
                    metadata,
                    created_at
                FROM performance_feedback
                WHERE tenant_id = %s
                  {where_filters}
                ORDER BY created_at DESC
                """,
                tuple(params)
            )
            rows = cur.fetchall()

    return {
        "performance_feedback": [
            serialize_performance_feedback(row) for row in rows
        ]
    }


@app.post("/improvement-candidates/{candidate_id}/evidence")
def add_candidate_evidence(candidate_id: str, payload: CandidateEvidenceCreate):
    candidate = get_candidate_context(candidate_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidate_evidence (
                    improvement_candidate_id,
                    evidence_type,
                    source_id,
                    description,
                    weight,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    improvement_candidate_id,
                    evidence_type,
                    source_id,
                    description,
                    weight,
                    metadata,
                    created_at
                """,
                (
                    candidate["id"],
                    payload.evidence_type,
                    payload.source_id,
                    payload.description,
                    payload.weight,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            evidence = cur.fetchone()
            conn.commit()

    emit_event(
        candidate["tenant_id"],
        "CandidateEvidenceAdded",
        "candidate_evidence",
        evidence[0],
        {
            "improvement_candidate_id": str(candidate["id"]),
            "evidence_type": payload.evidence_type,
            "source_id": payload.source_id,
        }
    )

    return {"evidence": serialize_candidate_evidence(evidence)}


@app.get("/improvement-candidates/{candidate_id}/evidence")
def list_candidate_evidence(candidate_id: str):
    get_candidate_context(candidate_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    improvement_candidate_id,
                    evidence_type,
                    source_id,
                    description,
                    weight,
                    metadata,
                    created_at
                FROM candidate_evidence
                WHERE improvement_candidate_id = %s
                ORDER BY created_at DESC
                """,
                (candidate_id,)
            )
            rows = cur.fetchall()

    return {"evidence": [serialize_candidate_evidence(row) for row in rows]}


@app.post("/improvement-candidates/{candidate_id}/evaluations")
def add_candidate_evaluation(candidate_id: str, payload: CandidateEvaluationCreate):
    if payload.verdict not in {"support", "reject", "inconclusive"}:
        raise HTTPException(status_code=400, detail="Invalid verdict")

    candidate = get_candidate_context(candidate_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidate_evaluations (
                    improvement_candidate_id,
                    evaluator_type,
                    score,
                    verdict,
                    rationale,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    improvement_candidate_id,
                    evaluator_type,
                    score,
                    verdict,
                    rationale,
                    metadata,
                    created_at
                """,
                (
                    candidate["id"],
                    payload.evaluator_type,
                    payload.score,
                    payload.verdict,
                    payload.rationale,
                    psycopg.types.json.Jsonb(payload.metadata),
                )
            )
            evaluation = cur.fetchone()
            conn.commit()

    emit_event(
        candidate["tenant_id"],
        "CandidateEvaluated",
        "candidate_evaluation",
        evaluation[0],
        {
            "improvement_candidate_id": str(candidate["id"]),
            "verdict": payload.verdict,
            "score": payload.score,
        }
    )

    return {"evaluation": serialize_candidate_evaluation(evaluation)}


@app.get("/improvement-candidates/{candidate_id}/evaluations")
def list_candidate_evaluations(candidate_id: str):
    get_candidate_context(candidate_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    improvement_candidate_id,
                    evaluator_type,
                    score,
                    verdict,
                    rationale,
                    metadata,
                    created_at
                FROM candidate_evaluations
                WHERE improvement_candidate_id = %s
                ORDER BY created_at DESC
                """,
                (candidate_id,)
            )
            rows = cur.fetchall()

    return {"evaluations": [serialize_candidate_evaluation(row) for row in rows]}


@app.post("/evolution/analyse/{candidate_id}")
def analyse_evolution_candidate(candidate_id: str):
    candidate = get_candidate_context(candidate_id)
    try:
        analysis = analyse_candidate(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    emit_event(
        candidate["tenant_id"],
        "EvolutionCandidateAnalysed",
        "improvement_candidate",
        candidate["id"],
        {
            "recommendation": analysis["recommendation"],
            "evidence_score": analysis["evidence_score"],
            "supporting_evidence_count": analysis["supporting_evidence_count"],
        }
    )

    return {"analysis": analysis}


@app.post(
    "/evolution/proposals/from-candidate/{candidate_id}",
    summary="Create an evolution proposal with an automatically generated version",
)
def create_evolution_proposal(candidate_id: str):
    candidate = get_candidate_context(candidate_id)
    try:
        proposal = build_skill_proposal(candidate_id)
    except ProposalBuilderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    created = proposal.pop("_created", True)
    if created:
        emit_event(
            candidate["tenant_id"],
            "EvolutionProposalCreated",
            "evolution_proposal",
            proposal["id"],
            {
                "improvement_candidate_id": str(candidate["id"]),
                "target_skill_id": proposal["target_skill_id"],
                "proposed_version": proposal["proposed_version"],
            }
        )

    return {"evolution_proposal": proposal}


@app.get("/evolution/proposals")
def list_evolution_proposals(status: str = None, target_skill_id: str = None):
    filters = []
    params = []
    if status:
        filters.append("status = %s")
        params.append(status)
    if target_skill_id:
        filters.append("target_skill_id = %s")
        params.append(target_skill_id)

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    improvement_candidate_id,
                    proposal_type,
                    target_skill_id,
                    base_skill_version_id,
                    proposed_version,
                    proposed_content,
                    status,
                    created_by,
                    approved_by,
                    approval_comment,
                    created_at,
                    approved_at
                FROM evolution_proposals
                {where_clause}
                ORDER BY created_at DESC
                """,
                tuple(params)
            )
            rows = cur.fetchall()

    return {
        "evolution_proposals": [
            serialize_evolution_proposal(row) for row in rows
        ]
    }


@app.get("/evolution/proposals/{proposal_id}")
def get_evolution_proposal(proposal_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    improvement_candidate_id,
                    proposal_type,
                    target_skill_id,
                    base_skill_version_id,
                    proposed_version,
                    proposed_content,
                    status,
                    created_by,
                    approved_by,
                    approval_comment,
                    created_at,
                    approved_at
                FROM evolution_proposals
                WHERE id = %s
                """,
                (proposal_id,)
            )
            proposal = cur.fetchone()

            if not proposal:
                raise HTTPException(status_code=404, detail="Evolution proposal not found")

            proposal_data = serialize_evolution_proposal(proposal)
            cur.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    candidate_type,
                    title,
                    body,
                    source_task_id,
                    source_agent_run_id,
                    status,
                    reviewed_by,
                    review_comment,
                    metadata,
                    created_at,
                    reviewed_at
                FROM improvement_candidates
                WHERE id = %s
                """,
                (proposal[1],)
            )
            candidate = cur.fetchone()
            cur.execute(
                """
                SELECT
                    id,
                    improvement_candidate_id,
                    evidence_type,
                    source_id,
                    description,
                    weight,
                    metadata,
                    created_at
                FROM candidate_evidence
                WHERE improvement_candidate_id = %s
                ORDER BY created_at DESC
                """,
                (proposal[1],)
            )
            evidence = cur.fetchall()
            cur.execute(
                """
                SELECT
                    id,
                    improvement_candidate_id,
                    evaluator_type,
                    score,
                    verdict,
                    rationale,
                    metadata,
                    created_at
                FROM candidate_evaluations
                WHERE improvement_candidate_id = %s
                ORDER BY created_at DESC
                """,
                (proposal[1],)
            )
            evaluations = cur.fetchall()

    return {
        "evolution_proposal": proposal_data,
        "candidate": serialize_improvement_candidate(candidate),
        "evidence": [serialize_candidate_evidence(row) for row in evidence],
        "evaluations": [
            serialize_candidate_evaluation(row) for row in evaluations
        ],
    }


@app.post("/evolution/proposals/{proposal_id}/approve")
def approve_evolution_proposal_endpoint(
    proposal_id: str,
    payload: EvolutionProposalReview
):
    try:
        proposal, skill_version = approve_evolution_proposal(
            proposal_id,
            payload.reviewed_by,
            payload.comment,
        )
    except (ProposalNotFoundError, TargetSkillNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SkillVersionContentConflictError:
        raise HTTPException(
            status_code=409,
            detail="Skill version already exists with different content",
        )
    except RejectedProposalError:
        raise HTTPException(
            status_code=409,
            detail="Rejected proposal cannot be approved",
        )

    return {
        "evolution_proposal": proposal,
        "skill_version": skill_version,
    }


@app.post("/evolution/proposals/{proposal_id}/reject")
def reject_evolution_proposal_endpoint(
    proposal_id: str,
    payload: EvolutionProposalReview
):
    try:
        proposal = reject_evolution_proposal(
            proposal_id,
            payload.reviewed_by,
            payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    candidate = get_candidate_context(proposal["improvement_candidate_id"])
    emit_event(
        candidate["tenant_id"],
        "EvolutionProposalRejected",
        "evolution_proposal",
        proposal["id"],
        {
            "target_skill_id": proposal["target_skill_id"],
            "reviewed_by": payload.reviewed_by,
        }
    )

    return {"evolution_proposal": proposal}


@app.post("/skills/{skill_slug}/versions/{version}/restore")
def restore_skill_version(
    skill_slug: str,
    version: str,
    payload: EvolutionProposalReview
):
    try:
        restored = restore_skill_version_status(skill_slug, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    emit_event(
        None,
        "SkillVersionRestored",
        "skill_version",
        restored["id"],
        {
            "skill_slug": skill_slug,
            "version": version,
            "reviewed_by": payload.reviewed_by,
            "comment": payload.comment,
        }
    )

    return {"skill_version": restored}


def get_skill_with_versions(skill_slug: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, slug
                FROM skills
                WHERE slug = %s
                """,
                (skill_slug,),
            )
            skill = cur.fetchone()
            if not skill:
                raise HTTPException(status_code=404, detail="Skill not found")

            cur.execute(
                """
                SELECT id, skill_id, version, status, content, created_at
                FROM skill_versions
                WHERE skill_id = %s
                """,
                (skill[0],),
            )
            versions = cur.fetchall()

    return skill, versions


def get_approved_skill_version(skill_slug: str):
    skill, versions = get_skill_with_versions(skill_slug)
    approved_versions = [version for version in versions if version[3] == "approved"]
    if not approved_versions:
        raise HTTPException(status_code=404, detail="Approved skill version not found")

    approved = max(approved_versions, key=lambda row: parse_semantic_version(row[2]))
    return skill, approved


def next_available_skill_version(conn, skill_id):
    latest = get_latest_skill_version(conn, skill_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Skill version not found")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT version
            FROM skill_versions
            WHERE skill_id = %s
            """,
            (skill_id,),
        )
        existing_versions = {row[0] for row in cur.fetchall()}

    next_version = next_minor_version(latest[2])
    while next_version in existing_versions:
        next_version = next_minor_version(next_version)
    return next_version


@app.get("/skills/{skill_slug}/integrity")
def get_skill_integrity(skill_slug: str):
    skill, approved = get_approved_skill_version(skill_slug)
    report = skill_integrity_report(approved[4])
    return {
        "skill_slug": skill[2],
        "approved_version": approved[2],
        **report,
    }


@app.post("/skills/{skill_slug}/repair-preview")
def preview_skill_repair(skill_slug: str):
    skill, approved = get_approved_skill_version(skill_slug)
    preview = build_repair_preview(approved[4])
    return {
        "skill_slug": skill[2],
        "before": {
            "version": approved[2],
            "improvement_section_count": preview["before"]["improvement_section_count"],
            "healthy": preview["before"]["healthy"],
            "issues": preview["before"]["issues"],
        },
        "after": {
            "improvement_section_count": preview["after"]["improvement_section_count"],
            "healthy": preview["after"]["healthy"],
            "issues": preview["after"]["issues"],
            "content": preview["after"]["content"],
        },
        "changes": preview["changes"],
    }


@app.post("/skills/{skill_slug}/repair")
def repair_skill(skill_slug: str, payload: EvolutionProposalReview):
    skill, approved = get_approved_skill_version(skill_slug)
    preview = build_repair_preview(approved[4])
    if preview["before"]["healthy"]:
        raise HTTPException(status_code=409, detail="No repair needed")
    if not preview["after"]["healthy"]:
        raise HTTPException(status_code=409, detail="Repair preview is still unhealthy")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            new_version = next_available_skill_version(conn, skill[0])
            cur.execute(
                """
                UPDATE skill_versions
                SET status = 'superseded'
                WHERE skill_id = %s AND status = 'approved'
                """,
                (skill[0],),
            )
            cur.execute(
                """
                INSERT INTO skill_versions (
                    skill_id,
                    version,
                    status,
                    content,
                    change_summary
                )
                VALUES (%s, %s, 'approved', %s, %s)
                RETURNING id, skill_id, version, status, content, created_at
                """,
                (
                    skill[0],
                    new_version,
                    preview["after"]["content"],
                    payload.comment,
                ),
            )
            repaired = cur.fetchone()
            conn.commit()

    emit_event(
        None,
        "SkillIntegrityRepairCreated",
        "skill_version",
        repaired[0],
        {
            "skill_slug": skill_slug,
            "from_version": approved[2],
            "to_version": repaired[2],
            "reviewed_by": payload.reviewed_by,
            "comment": payload.comment,
        },
    )
    emit_event(
        None,
        "SkillVersionCreated",
        "skill_version",
        repaired[0],
        {
            "skill_slug": skill_slug,
            "version": repaired[2],
            "status": "approved",
        },
    )
    emit_event(
        None,
        "SkillVersionApproved",
        "skill_version",
        repaired[0],
        {
            "skill_slug": skill_slug,
            "version": repaired[2],
        },
    )

    return {
        "skill_version": serialize_skill_version(repaired),
        "repair": {
            "from_version": approved[2],
            "to_version": repaired[2],
            "changes": preview["changes"],
        },
    }


@app.post("/skills/{skill_slug}/versions")
def create_skill_version(skill_slug: str, payload: SkillVersionCreate):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM skills WHERE slug = %s", (skill_slug,))
            skill = cur.fetchone()

            if not skill:
                raise HTTPException(status_code=404, detail="Skill not found")

            cur.execute(
                """
                SELECT id
                FROM skill_versions
                WHERE skill_id = %s AND version = %s
                """,
                (skill[0], payload.version)
            )
            existing_version = cur.fetchone()

            if existing_version:
                raise HTTPException(
                    status_code=409,
                    detail="Skill version already exists"
                )

            cur.execute(
                """
                INSERT INTO skill_versions (skill_id, version, status, content)
                VALUES (%s, %s, %s, %s)
                RETURNING id, skill_id, version, status, content, created_at
                """,
                (skill[0], payload.version, payload.status, payload.content)
            )
            version = cur.fetchone()
            conn.commit()

    emit_event(
        None,
        "SkillVersionCreated",
        "skill_version",
        version[0],
        {
            "skill_slug": skill_slug,
            "version": payload.version,
            "status": payload.status,
        }
    )

    return {"skill_version": serialize_skill_version(version)}


@app.post("/skills/{skill_slug}/versions/{version}/approve")
def approve_skill_version(skill_slug: str, version: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sv.id
                FROM skill_versions sv
                JOIN skills s ON s.id = sv.skill_id
                WHERE s.slug = %s AND sv.version = %s
                """,
                (skill_slug, version)
            )
            skill_version = cur.fetchone()

            if not skill_version:
                raise HTTPException(status_code=404, detail="Skill version not found")

            cur.execute(
                """
                UPDATE skill_versions
                SET status = 'approved'
                WHERE id = %s
                RETURNING id, skill_id, version, status, content, created_at
                """,
                (skill_version[0],)
            )
            approved_version = cur.fetchone()
            conn.commit()

    emit_event(
        None,
        "SkillVersionApproved",
        "skill_version",
        approved_version[0],
        {
            "skill_slug": skill_slug,
            "version": version,
            "status": "approved",
        }
    )

    return {"skill_version": serialize_skill_version(approved_version)}


@app.post("/performance-data/{tenant_slug}/google-ads/import")
async def import_google_ads_performance_data(
    tenant_slug: str,
    file: UploadFile = File(...),
    created_by: str | None = Form(default=None),
):
    tenant = get_tenant_by_slug(tenant_slug)
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    emit_event(
        tenant["id"],
        "PerformanceImportStarted",
        "performance_import",
        None,
        {"channel": "google_ads", "filename": file.filename},
    )
    try:
        with get_db_connection() as conn:
            result = import_google_ads_csv(
                conn,
                tenant["id"],
                file.filename,
                file_bytes,
                created_by,
            )
    except DuplicateImportError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CsvValidationError as exc:
        emit_event(
            tenant["id"],
            "PerformanceImportFailed",
            "performance_import",
            None,
            {"channel": "google_ads", "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc))

    event_type = (
        "PerformanceImportFailed"
        if result.status == "failed"
        else "PerformanceImportCompleted"
    )
    emit_event(
        tenant["id"],
        event_type,
        "performance_import",
        result.import_id,
        {
            "channel": result.channel,
            "status": result.status,
            "row_count": result.row_count,
            "valid_row_count": result.valid_row_count,
            "invalid_row_count": result.invalid_row_count,
        },
    )
    return {"performance_import": result.__dict__}


@app.get("/performance-data/{tenant_slug}/imports")
def list_performance_imports(tenant_slug: str, channel: str = None):
    tenant = get_tenant_by_slug(tenant_slug)
    with get_db_connection() as conn:
        imports = get_imports_for_tenant(conn, tenant["id"], channel)
    return {"imports": imports}


@app.get("/performance-data/{tenant_slug}/imports/{import_id}")
def get_performance_import(tenant_slug: str, import_id: str):
    tenant = get_tenant_by_slug(tenant_slug)
    with get_db_connection() as conn:
        performance_import = get_import_by_id(conn, tenant["id"], import_id)
    if not performance_import:
        raise HTTPException(status_code=404, detail="Performance import not found")
    return {"performance_import": performance_import}


@app.get("/performance-data/{tenant_slug}/google-ads/summary")
def get_google_ads_performance_summary(
    tenant_slug: str,
    date_from: str = None,
    date_to: str = None,
    campaign_id: str = None,
    campaign_status: str = None,
):
    tenant = get_tenant_by_slug(tenant_slug)
    filters = PerformanceFilters(
        date_from=date_from,
        date_to=date_to,
        campaign_id=campaign_id,
        campaign_status=campaign_status,
    )
    with get_db_connection() as conn:
        rows = get_google_ads_summary_data(conn, tenant["id"], filters)
    try:
        summary = calculate_google_ads_summary(rows, filters)
    except NoPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"summary": summary}


@app.post("/tasks")
def create_task(payload: TaskCreate):
    tenant = get_tenant_by_slug(payload.tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (tenant_id, title, status, input)
                VALUES (%s, %s, 'queued', %s)
                RETURNING id, status, created_at
                """,
                (tenant["id"], payload.title, psycopg.types.json.Jsonb(payload.input))
            )

            row = cur.fetchone()
            conn.commit()

    emit_event(
        tenant["id"],
        "TaskCreated",
        "task",
        row[0],
        {"title": payload.title, "input": payload.input}
    )

    return {
        "task": {
            "id": str(row[0]),
            "tenant_id": str(tenant["id"]),
            "title": payload.title,
            "status": row[1],
            "input": payload.input,
            "created_at": row[2].isoformat()
        }
    }

@app.get("/tasks/{tenant_slug}")
def list_tasks(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, input, created_at
                FROM tasks
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant["id"],)
            )
            rows = cur.fetchall()

    return {
        "tasks": [serialize_task(row) for row in rows]
    }


@app.post("/task-engine/run-next/{tenant_slug}")
def run_next_task(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, input, created_at
                FROM tasks
                WHERE tenant_id = %s AND status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE
                """,
                (tenant["id"],)
            )
            task = cur.fetchone()

            if not task:
                conn.commit()
                return {"message": "No queued tasks"}

            task_id = task[0]
            execution_package = plan_execution(serialize_task(task), tenant)
            try:
                execution_package = execute_execution_tools(
                    execution_package,
                    tenant,
                    task_id,
                )
            except HTTPException as exc:
                cur.execute(
                    """
                    UPDATE tasks
                    SET status = 'failed'
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id, title, status, input, created_at
                    """,
                    (task_id, tenant["id"]),
                )
                failed_task = cur.fetchone()
                conn.commit()
                return {
                    "task": serialize_task(failed_task),
                    "error": exc.detail,
                }
            skills = execution_package["skills"]
            memory = execution_package["memory"]
            system_prompt, user_prompt = build_prompts(execution_package)
            provider = execution_package["model"]["provider"]
            model_name = execution_package["model"]["model_name"]
            agent_run_input = {
                **execution_package,
                "prompt_metadata": {
                    "system_prompt_length": len(system_prompt),
                    "user_prompt_length": len(user_prompt),
                    "output_format": "json",
                },
            }
            logs = [
                f"provider selected: {provider}",
                f"model selected: {model_name}",
                "execution started",
            ]

            cur.execute(
                """
                INSERT INTO agent_runs (
                    tenant_id,
                    task_id,
                    agent_template_id,
                    status,
                    input,
                    logs
                )
                VALUES (%s, %s, %s, 'running', %s, %s)
                RETURNING id, task_id, agent_template_id, status, input, output, logs, created_at
                """,
                (
                    tenant["id"],
                    task_id,
                    None,
                    psycopg.types.json.Jsonb(agent_run_input),
                    psycopg.types.json.Jsonb(logs),
                )
            )
            agent_run = cur.fetchone()
            conn.commit()

    emit_event(
        tenant["id"],
        "ExecutionPlanned",
        "task",
        task_id,
        {
            "agent_run_id": str(agent_run[0]),
            "capability_id": execution_package["capability"]["id"],
            "worker_id": execution_package["worker"]["id"],
            "model": execution_package["model"],
        }
    )
    emit_event(
        tenant["id"],
        "CapabilityResolved",
        "capability",
        execution_package["capability"]["id"],
        {
            "task_id": str(task_id),
            "slug": execution_package["capability"]["slug"],
        }
    )
    emit_event(
        tenant["id"],
        "WorkerResolved",
        "worker",
        execution_package["worker"]["id"],
        {
            "task_id": str(task_id),
            "capability_id": execution_package["capability"]["id"],
            "channel": execution_package["worker"]["channel"],
        }
    )
    emit_event(
        tenant["id"],
        "ModelResolved",
        "model_route",
        execution_package["model"]["id"],
        {
            "task_id": str(task_id),
            "provider": provider,
            "model_name": model_name,
        }
    )
    emit_event(
        tenant["id"],
        "PermissionsResolved",
        "task",
        task_id,
        {
            "agent_run_id": str(agent_run[0]),
            "permissions": execution_package["permissions"],
            "tools": execution_package["tools"],
        }
    )
    emit_event(
        tenant["id"],
        "MemoryResolved",
        "task",
        task_id,
        {
            "agent_run_id": str(agent_run[0]),
            "memory_item_ids": [item["id"] for item in memory],
        }
    )
    emit_event(
        tenant["id"],
        "SkillsResolved",
        "capability",
        execution_package["capability"]["id"],
        {
            "task_id": str(task_id),
            "capability_id": execution_package["capability"]["id"],
            "skills": [
                {
                    "skill_id": skill["skill_id"],
                    "skill_version_id": skill["skill_version_id"],
                    "slug": skill["slug"],
                    "version": skill["version"],
                }
                for skill in skills
            ],
        }
    )
    emit_event(
        tenant["id"],
        "LLMExecutionStarted",
        "agent_run",
        agent_run[0],
        {
            "task_id": str(task_id),
            "agent_run_id": str(agent_run[0]),
            "provider": provider,
            "model": model_name,
        }
    )

    llm_result = None
    try:
        llm_result = LLMGateway().generate(
            provider,
            LLMRequest(
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                metadata={
                    "task_id": str(task_id),
                    "agent_run_id": str(agent_run[0]),
                    "capability": execution_package["capability"]["slug"],
                },
            )
        )
        output = normalize_llm_output(llm_result.text)
        performance_summary = execution_package["context"].get("performance_summary")
        if performance_summary:
            output["performance_snapshot"] = {
                "import_ids": performance_summary["data_quality"]["import_ids"],
                "date_from": performance_summary["period"]["date_from"],
                "date_to": performance_summary["period"]["date_to"],
                "totals": performance_summary["totals"],
                "calculated_metrics": performance_summary["calculated_metrics"],
            }
        logs.append("execution completed")
        logs.append({"llm": llm_usage_payload(llm_result)})

        emit_event(
            tenant["id"],
            "LLMExecutionCompleted",
            "agent_run",
            agent_run[0],
            {
                "task_id": str(task_id),
                "agent_run_id": str(agent_run[0]),
                "provider": provider,
                "model": model_name,
                "usage": {
                    "input_tokens": llm_result.usage.input_tokens,
                    "output_tokens": llm_result.usage.output_tokens,
                    "total_tokens": llm_result.usage.total_tokens,
                },
                "latency_ms": llm_result.latency_ms,
            }
        )
    except LLMProviderError as exc:
        error_type = type(exc).__name__
        output = normalize_llm_output(f"LLM execution failed: {error_type}")
        logs.append("execution failed")
        logs.append({"llm_error_type": error_type})
        emit_event(
            tenant["id"],
            "LLMExecutionFailed",
            "agent_run",
            agent_run[0],
            {
                "task_id": str(task_id),
                "agent_run_id": str(agent_run[0]),
                "provider": provider,
                "model": model_name,
                "error_type": error_type,
            }
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_runs
                SET status = 'completed', output = %s, logs = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, task_id, agent_template_id, status, input, output, logs, created_at
                """,
                (
                    psycopg.types.json.Jsonb(output),
                    psycopg.types.json.Jsonb(logs),
                    agent_run[0],
                    tenant["id"],
                )
            )
            completed_run = cur.fetchone()

            cur.execute(
                """
                UPDATE tasks
                SET status = 'needs_review'
                WHERE id = %s AND tenant_id = %s
                RETURNING id, title, status, input, created_at
                """,
                (task_id, tenant["id"])
            )
            updated_task = cur.fetchone()

            cur.execute(
                """
                INSERT INTO approvals (tenant_id, task_id, status, requested_by)
                VALUES (%s, %s, 'pending', %s)
                RETURNING id, task_id, status, requested_by, created_at
                """,
                (tenant["id"], task_id, "mock-worker")
            )
            approval = cur.fetchone()

            learning_candidate = first_learning_candidate(
                output,
                execution_package["task"]["title"]
            )
            cur.execute(
                """
                INSERT INTO learnings (tenant_id, scope, title, body, confidence)
                VALUES (%s, 'partner', %s, %s, 'medium')
                RETURNING id, scope, title, body, confidence, created_at
                """,
                (
                    tenant["id"],
                    learning_candidate["title"],
                    learning_candidate["body"],
                )
            )
            learning = cur.fetchone()

            cur.execute(
                """
                INSERT INTO memory_items (
                    tenant_id,
                    memory_type,
                    title,
                    body,
                    source,
                    confidence,
                    metadata
                )
                VALUES (%s, 'partner_learning', %s, %s, 'agent_run', 'medium', %s)
                RETURNING id, tenant_id, memory_type, title, body, source, status, confidence, metadata, created_at
                """,
                (
                    tenant["id"],
                    learning_candidate["title"],
                    learning_candidate["body"],
                    psycopg.types.json.Jsonb(
                        {
                            "task_id": str(task_id),
                            "agent_run_id": str(agent_run[0]),
                        }
                    ),
                )
            )
            memory_item = cur.fetchone()

            improvement_candidate = None
            candidate_evidence = None
            if output.get("learning_candidates"):
                active_skills = [
                    {
                        "skill_id": skill["skill_id"],
                        "skill_version_id": skill["skill_version_id"],
                        "slug": skill["slug"],
                        "version": skill["version"],
                    }
                    for skill in skills
                ]
                cur.execute(
                    """
                    INSERT INTO improvement_candidates (
                        tenant_id,
                        candidate_type,
                        title,
                        body,
                        source_task_id,
                        source_agent_run_id,
                        status,
                        metadata
                    )
                    VALUES (%s, 'skill_improvement', %s, %s, %s, %s, 'proposed', %s)
                    RETURNING
                        id,
                        tenant_id,
                        candidate_type,
                        title,
                        body,
                        source_task_id,
                        source_agent_run_id,
                        status,
                        reviewed_by,
                        review_comment,
                        metadata,
                        created_at,
                        reviewed_at
                    """,
                    (
                        tenant["id"],
                        f"Potential skill improvement from {execution_package['task']['title']}",
                        "Review whether this run suggests an update to the active skill.",
                        task_id,
                        agent_run[0],
                        psycopg.types.json.Jsonb(
                            {
                                "task_id": str(task_id),
                                "agent_run_id": str(agent_run[0]),
                                "active_skills": active_skills,
                            }
                        ),
                    )
                )
                improvement_candidate = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO candidate_evidence (
                        improvement_candidate_id,
                        evidence_type,
                        source_id,
                        description,
                        metadata
                    )
                    VALUES (%s, 'agent_run', %s, %s, %s)
                    RETURNING
                        id,
                        improvement_candidate_id,
                        evidence_type,
                        source_id,
                        description,
                        weight,
                        metadata,
                        created_at
                    """,
                    (
                        improvement_candidate[0],
                        agent_run[0],
                        learning_candidate["body"],
                        psycopg.types.json.Jsonb(
                            {
                                "task_id": str(task_id),
                                "agent_run_id": str(agent_run[0]),
                            }
                        ),
                    )
                )
                candidate_evidence = cur.fetchone()

            conn.commit()

    emit_event(
        tenant["id"],
        "AgentRunStarted",
        "agent_run",
        agent_run[0],
        {
            "task_id": str(task_id),
            "capability_id": execution_package["capability"]["id"],
            "worker_id": execution_package["worker"]["id"],
        }
    )
    emit_event(
        tenant["id"],
        "AgentRunCompleted",
        "agent_run",
        completed_run[0],
        {"task_id": str(task_id), "output": output}
    )
    emit_event(
        tenant["id"],
        "ApprovalRequested",
        "approval",
        approval[0],
        {"task_id": str(task_id), "agent_run_id": str(completed_run[0])}
    )
    emit_event(
        tenant["id"],
        "LearningCandidateCreated",
        "learning",
        learning[0],
        {"task_id": str(task_id), "learning_candidate": learning_candidate}
    )
    emit_event(
        tenant["id"],
        "MemoryItemCreated",
        "memory_item",
        memory_item[0],
        {
            "task_id": str(task_id),
            "agent_run_id": str(agent_run[0]),
            "memory_type": "partner_learning",
        }
    )
    if improvement_candidate:
        emit_event(
            tenant["id"],
            "ImprovementCandidateCreated",
            "improvement_candidate",
            improvement_candidate[0],
            {
                "task_id": str(task_id),
                "agent_run_id": str(agent_run[0]),
                "candidate_type": "skill_improvement",
            }
        )
    if candidate_evidence:
        emit_event(
            tenant["id"],
            "CandidateEvidenceAdded",
            "candidate_evidence",
            candidate_evidence[0],
            {
                "improvement_candidate_id": str(candidate_evidence[1]),
                "evidence_type": "agent_run",
                "source_id": str(candidate_evidence[3]),
            }
        )
    emit_event(
        tenant["id"],
        "TaskNeedsReview",
        "task",
        task_id,
        {"agent_run_id": str(completed_run[0]), "approval_id": str(approval[0])}
    )

    return {
        "task": serialize_task(updated_task),
        "agent_run": serialize_agent_run(completed_run),
        "output": output,
        "approval": serialize_approval(approval),
    }


@app.get("/events/{tenant_slug}")
def list_events(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, entity_type, entity_id, payload, created_at
                FROM events
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant["id"],)
            )
            rows = cur.fetchall()

    return {"events": [serialize_event(row) for row in rows]}


@app.get("/learnings/{tenant_slug}")
def list_learnings(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, scope, title, body, confidence, created_at
                FROM learnings
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant["id"],)
            )
            rows = cur.fetchall()

    return {"learnings": [serialize_learning(row) for row in rows]}


@app.get("/agent-runs/{tenant_slug}")
def list_agent_runs(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, task_id, agent_template_id, status, input, output, logs, created_at
                FROM agent_runs
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant["id"],)
            )
            rows = cur.fetchall()

    return {"agent_runs": [serialize_agent_run(row) for row in rows]}
