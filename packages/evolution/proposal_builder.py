from __future__ import annotations

import os

from packages.evolution.engine import (
    get_candidate,
    get_evaluations,
    get_evidence,
    serialize_candidate,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents",
)


class ProposalBuilderConflictError(ValueError):
    pass


class ImprovementCandidateAlreadyAppliedError(ProposalBuilderConflictError):
    pass


class DuplicateImprovementContentError(ProposalBuilderConflictError):
    pass


class BaseSkillIntegrityError(ProposalBuilderConflictError):
    pass


def build_skill_proposal(candidate_id, database_url=None):
    database_url = database_url or DATABASE_URL
    import psycopg
    from packages.evolution.versioning import (
        SkillIntegrityError,
        get_latest_skill_version,
        validate_skill_base_content,
    )

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            candidate = get_candidate(cur, candidate_id)
            if candidate["candidate_type"] != "skill_improvement":
                raise ValueError("Candidate is not a skill improvement")
            if candidate["status"] != "approved":
                raise ValueError("Candidate must be approved before proposal creation")

            active_skills = candidate.get("metadata", {}).get("active_skills") or []
            if not active_skills:
                raise ValueError("Candidate has no active skill metadata")

            target_skill_id = active_skills[0]["skill_id"]
            applied_version = get_applied_candidate_version(
                cur,
                target_skill_id,
                candidate_id,
            )
            if applied_version:
                raise ImprovementCandidateAlreadyAppliedError(
                    "Improvement candidate has already been applied to this skill"
                )

            existing_draft = get_existing_draft_proposal(
                cur,
                candidate_id,
                target_skill_id,
            )
            if existing_draft:
                proposal = serialize_proposal(existing_draft)
                proposal["_created"] = False
                return proposal

            latest_version = get_latest_skill_version(conn, target_skill_id)
            if not latest_version:
                raise ValueError("No skill version found")

            cur.execute(
                """
                SELECT id, skill_id, version, status, content, created_at
                FROM skill_versions
                WHERE skill_id = %s AND status = 'approved'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (target_skill_id,),
            )
            base_version = cur.fetchone()
            if not base_version:
                raise ValueError("No approved skill version found")
            try:
                validate_skill_base_content(base_version[4])
            except SkillIntegrityError as exc:
                raise BaseSkillIntegrityError(
                    "Approved base skill failed integrity validation"
                ) from exc

            proposed_version = resolve_next_proposal_version(
                cur,
                target_skill_id,
                latest_version[2],
            )
            evidence = get_evidence(cur, candidate_id)
            evaluations = get_evaluations(cur, candidate_id)
            proposed_content = draft_skill_content(
                base_version[4],
                candidate,
                evidence,
                evaluations,
            )

            cur.execute(
                """
                INSERT INTO evolution_proposals (
                    improvement_candidate_id,
                    proposal_type,
                    target_skill_id,
                    base_skill_version_id,
                    proposed_version,
                    proposed_content,
                    status
                )
                VALUES (%s, 'skill_version', %s, %s, %s, %s, 'draft')
                RETURNING
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
                """,
                (
                    candidate_id,
                    target_skill_id,
                    base_version[0],
                    proposed_version,
                    proposed_content,
                ),
            )
            proposal = serialize_proposal(cur.fetchone())
            proposal["_created"] = True
            conn.commit()

    return proposal


def get_applied_candidate_version(cur, target_skill_id, candidate_id):
    cur.execute(
        """
        SELECT id
        FROM skill_versions
        WHERE skill_id = %s
          AND status = 'approved'
          AND source_improvement_candidate_id = %s
        LIMIT 1
        """,
        (target_skill_id, candidate_id),
    )
    return cur.fetchone()


def get_existing_draft_proposal(cur, candidate_id, target_skill_id):
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
        WHERE improvement_candidate_id = %s
          AND target_skill_id = %s
          AND status = 'draft'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (candidate_id, target_skill_id),
    )
    return cur.fetchone()


def resolve_next_proposal_version(cur, target_skill_id, latest_version):
    from packages.evolution.versioning import next_minor_version

    cur.execute(
        """
        SELECT version
        FROM skill_versions
        WHERE skill_id = %s
        UNION
        SELECT proposed_version AS version
        FROM evolution_proposals
        WHERE target_skill_id = %s
          AND status <> 'rejected'
        """,
        (target_skill_id, target_skill_id),
    )
    existing_versions = {row[0] for row in cur.fetchall()}

    proposed_version = next_minor_version(latest_version)
    while proposed_version in existing_versions:
        proposed_version = next_minor_version(proposed_version)

    return proposed_version


def draft_skill_content(current_content, candidate, evidence, evaluations):
    section = build_improvement_section(candidate, evidence, evaluations)
    marker = improvement_marker(candidate["id"])
    if marker in current_content:
        raise ImprovementCandidateAlreadyAppliedError(
            "Improvement candidate has already been applied to this skill"
        )
    if normalize_markdown(section_without_marker(section)) in normalize_markdown(current_content):
        raise DuplicateImprovementContentError(
            "Improvement content already exists in skill"
        )

    return "\n\n".join([current_content.rstrip(), section])


def build_improvement_section(candidate, evidence, evaluations):
    evidence_lines = [
        f"- {item['evidence_type']}: {item.get('description') or 'No description'}"
        for item in evidence
    ]
    evaluation_lines = [
        f"- {item['verdict']} ({item.get('score')}): {item.get('rationale') or 'No rationale'}"
        for item in evaluations
    ]

    return "\n\n".join(
        [
            "## Evidence-backed improvement",
            f"Candidate: {candidate['title']}",
            candidate["body"],
            "Evidence:",
            "\n".join(evidence_lines) if evidence_lines else "- No evidence provided",
            "Evaluations:",
            "\n".join(evaluation_lines) if evaluation_lines else "- No evaluations provided",
            "Human approval remains required before any external change.",
            improvement_marker(candidate["id"]),
        ]
    )


def improvement_marker(candidate_id):
    return f"<!-- sdq-improvement-candidate:{candidate_id} -->"


def section_without_marker(section):
    lines = [
        line for line in section.splitlines()
        if not line.strip().startswith("<!-- sdq-improvement-candidate:")
    ]
    return "\n".join(lines)


def normalize_markdown(content):
    return " ".join(content.split())


def serialize_proposal(row):
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
