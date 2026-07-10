from __future__ import annotations

import os

from packages.evolution.evaluator import evaluate_candidate

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents",
)


def analyse_candidate(candidate_id, database_url=None):
    database_url = database_url or DATABASE_URL
    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            candidate = get_candidate(cur, candidate_id)
            evidence = get_evidence(cur, candidate_id)
            evaluations = get_evaluations(cur, candidate_id)

    analysis = evaluate_candidate(evidence, evaluations)
    return {
        "candidate": candidate,
        "evidence": evidence,
        "evaluations": evaluations,
        **analysis,
    }


def get_candidate(cur, candidate_id):
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
        (candidate_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Improvement candidate not found")
    return serialize_candidate(row)


def get_evidence(cur, candidate_id):
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
        (candidate_id,),
    )
    return [serialize_evidence(row) for row in cur.fetchall()]


def get_evaluations(cur, candidate_id):
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
        (candidate_id,),
    )
    return [serialize_evaluation(row) for row in cur.fetchall()]


def serialize_candidate(row):
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


def serialize_evidence(row):
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


def serialize_evaluation(row):
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
