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
    agent_template = get_default_agent_template()

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
            task_input = task[3]
            run_input = {
                "task_id": str(task_id),
                "task_title": task[1],
                "task_input": task_input,
                "agent_template": agent_template["name"],
            }

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
                    agent_template["id"],
                    psycopg.types.json.Jsonb(run_input),
                    psycopg.types.json.Jsonb(["Mock worker started"]),
                )
            )
            agent_run = cur.fetchone()

            output = {
                "summary": f"Mock analysis completed for: {task[1]}",
                "recommendations": [
                    "Review high-spend segments for wasted budget.",
                    "Prioritize optimizations with clear conversion impact.",
                ],
                "learning_candidate": {
                    "title": f"Learning from {task[1]}",
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

            conn.commit()

    emit_event(
        tenant["id"],
        "AgentRunStarted",
        "agent_run",
        agent_run[0],
        {"task_id": str(task_id), "agent_template_id": str(agent_template["id"])}
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
