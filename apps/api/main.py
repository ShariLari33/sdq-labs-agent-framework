import os
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="SDQ Labs Agent Framework API")

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
    tools = ["mock_performance_reader"]

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

@app.get("/health")
def health():
    return {"status": "ok", "service": "sdq-agent-framework-api"}

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
            skills = execution_package["skills"]
            memory = execution_package["memory"]

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
                    psycopg.types.json.Jsonb(execution_package),
                    psycopg.types.json.Jsonb(["Mock worker started"]),
                )
            )
            agent_run = cur.fetchone()

            output = {
                "summary": f"Mock analysis completed for: {execution_package['task']['title']}",
                "recommendations": [
                    "Review high-spend segments for wasted budget.",
                    "Prioritize optimizations with clear conversion impact.",
                ],
                "learning_candidate": {
                    "title": f"Learning from {execution_package['task']['title']}",
                    "body": "Mock worker suggests saving this task pattern for future partner optimizations.",
                },
                "approval_required": True,
            }

            cur.execute(
                """
                UPDATE agent_runs
                SET status = 'completed', output = %s, logs = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, task_id, agent_template_id, status, input, output, logs, created_at
                """,
                (
                    psycopg.types.json.Jsonb(output),
                    psycopg.types.json.Jsonb(["Mock worker started", "Mock worker completed"]),
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

            learning_candidate = output["learning_candidate"]
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
            "provider": execution_package["model"]["provider"],
            "model_name": execution_package["model"]["model_name"],
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
