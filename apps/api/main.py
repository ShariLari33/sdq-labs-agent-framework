import os
import psycopg
from fastapi import FastAPI

app = FastAPI(title="SDQ Labs Agent Framework API")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents"
)

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
