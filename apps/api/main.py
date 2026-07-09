import os
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SDQ Labs Agent Framework API")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents"
)

class TaskCreate(BaseModel):
    tenant_slug: str
    title: str
    input: dict = {}

@app.get("/health")
def health():
    return {"status": "ok", "service": "sdq-agent-framework-api"}

@app.get("/tenants")
def get_tenants():
    with psycopg.connect(DATABASE_URL) as conn:
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
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (payload.tenant_slug,))
            tenant = cur.fetchone()

            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            tenant_id = tenant[0]

            cur.execute(
                """
                INSERT INTO tasks (tenant_id, title, status, input)
                VALUES (%s, %s, 'queued', %s)
                RETURNING id, status, created_at
                """,
                (tenant_id, payload.title, psycopg.types.json.Jsonb(payload.input))
            )

            row = cur.fetchone()
            conn.commit()

    return {
        "task": {
            "id": str(row[0]),
            "tenant_id": str(tenant_id),
            "title": payload.title,
            "status": row[1],
            "input": payload.input,
            "created_at": row[2].isoformat()
        }
    }

@app.get("/tasks/{tenant_slug}")
def list_tasks(tenant_slug: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (tenant_slug,))
            tenant = cur.fetchone()

            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            cur.execute(
                """
                SELECT id, title, status, input, created_at
                FROM tasks
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant[0],)
            )
            rows = cur.fetchall()

    return {
        "tasks": [
            {
                "id": str(row[0]),
                "title": row[1],
                "status": row[2],
                "input": row[3],
                "created_at": row[4].isoformat()
            }
            for row in rows
        ]
    }
