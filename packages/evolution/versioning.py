from __future__ import annotations

import os
import re

from packages.evolution.proposal_builder import serialize_proposal

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sdq:sdq_dev_password@postgres:5432/sdq_agents",
)


class EvolutionVersioningError(Exception):
    pass


class ProposalNotFoundError(EvolutionVersioningError):
    pass


class TargetSkillNotFoundError(EvolutionVersioningError):
    pass


class SkillVersionContentConflictError(EvolutionVersioningError):
    pass


class RejectedProposalError(EvolutionVersioningError):
    pass


class InvalidSemanticVersionError(EvolutionVersioningError, ValueError):
    pass


class SkillIntegrityError(EvolutionVersioningError, ValueError):
    def __init__(self, message, issues=None):
        super().__init__(message)
        self.issues = issues or [message]


class NoSkillRepairNeededError(SkillIntegrityError):
    pass


def parse_semantic_version(version):
    parts = version.split(".")
    if len(parts) != 3:
        raise InvalidSemanticVersionError(
            "Version must use major.minor.patch format"
        )
    for part in parts:
        if not part.isdecimal() or (len(part) > 1 and part.startswith("0")):
            raise InvalidSemanticVersionError(
                "Version must use major.minor.patch format"
            )
    try:
        major, minor, patch = [int(part) for part in parts]
    except ValueError as exc:
        raise InvalidSemanticVersionError(
            "Version must use major.minor.patch format"
        ) from exc
    if major < 0 or minor < 0 or patch < 0:
        raise InvalidSemanticVersionError("Version numbers must be non-negative")
    return major, minor, patch


def next_minor_version(current_version: str) -> str:
    major, minor, patch = parse_semantic_version(current_version)
    return f"{major}.{minor + 1}.0"


def next_version(current_version):
    return next_minor_version(current_version)


def get_latest_skill_version(conn, skill_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, skill_id, version, status, content, created_at
            FROM skill_versions
            WHERE skill_id = %s
            """,
            (skill_id,),
        )
        versions = cur.fetchall()

    if not versions:
        return None

    return max(versions, key=lambda row: parse_semantic_version(row[2]))


def count_improvement_sections(content: str) -> int:
    return content.count("## Evidence-backed improvement") if content else 0


def extract_provenance_markers(content: str) -> list[str]:
    if not content:
        return []
    return re.findall(r"<!--\s*sdq-improvement-candidate:([^>\s]+)\s*-->", content)


def duplicate_provenance_markers(content: str) -> list[str]:
    markers = extract_provenance_markers(content)
    return sorted({marker for marker in markers if markers.count(marker) > 1})


def has_human_approval_rule(content: str) -> bool:
    return bool(content and "human approval" in content.lower())


def skill_integrity_report(content: str) -> dict:
    markers = extract_provenance_markers(content or "")
    duplicate_markers = sorted(
        {marker for marker in markers if markers.count(marker) > 1}
    )
    issues = []
    if not content or not content.strip():
        issues.append("Skill content is empty")
    if count_improvement_sections(content or "") > 1:
        issues.append("Skill content has more than one evidence-backed improvement section")
    if duplicate_markers:
        issues.append("Skill content has duplicate provenance markers")
    if not has_human_approval_rule(content or ""):
        issues.append("Skill content is missing human approval rule")

    return {
        "improvement_section_count": count_improvement_sections(content or ""),
        "provenance_markers": markers,
        "duplicate_provenance_markers": duplicate_markers,
        "has_human_approval_rule": has_human_approval_rule(content or ""),
        "healthy": not issues,
        "issues": issues,
    }


def validate_skill_base_content(content: str):
    report = skill_integrity_report(content)
    if not report["healthy"]:
        raise SkillIntegrityError(
            "Approved base skill failed integrity validation",
            report["issues"],
        )
    return True


def split_improvement_blocks(content: str):
    heading = "## Evidence-backed improvement"
    if heading not in content:
        return content, []

    first_index = content.find(heading)
    prefix = content[:first_index].rstrip()
    remainder = content[first_index:]
    starts = [match.start() for match in re.finditer(re.escape(heading), remainder)]
    blocks = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(remainder)
        blocks.append(remainder[start:end].strip())
    return prefix, blocks


def normalize_skill_block(content: str) -> str:
    return " ".join((content or "").split())


def build_repair_preview(content: str) -> dict:
    before = skill_integrity_report(content)
    prefix, blocks = split_improvement_blocks(content or "")
    unique_blocks = []
    seen_blocks = set()
    changes = []

    for block in blocks:
        normalized = normalize_skill_block(block)
        if normalized in seen_blocks:
            changes.append("Removed duplicate evidence-backed improvement block")
            continue
        seen_blocks.add(normalized)
        unique_blocks.append(block)

    parts = [part for part in [prefix, *unique_blocks] if part]
    repaired_content = "\n\n".join(parts).rstrip()
    after = skill_integrity_report(repaired_content)
    return {
        "before": before,
        "after": {
            **after,
            "content": repaired_content,
        },
        "changes": changes,
    }


def determine_approval_action(proposal_status, existing_version, proposed_content):
    if proposal_status == "rejected":
        raise RejectedProposalError("Rejected proposal cannot be approved")
    if existing_version and existing_version["content"] != proposed_content:
        raise SkillVersionContentConflictError(
            "Skill version already exists with different content"
        )
    if proposal_status == "approved":
        return "already_approved"
    if existing_version is None:
        return "create"
    if existing_version["status"] == "approved":
        return "reuse_approved"
    return "reuse_existing"


def approve_proposal(proposal_id, reviewed_by, comment, database_url=None):
    database_url = database_url or DATABASE_URL
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ep.id,
                    ep.improvement_candidate_id,
                    ep.proposal_type,
                    ep.target_skill_id,
                    ep.base_skill_version_id,
                    ep.proposed_version,
                    ep.proposed_content,
                    ep.status,
                    ep.created_by,
                    ep.approved_by,
                    ep.approval_comment,
                    ep.created_at,
                    ep.approved_at,
                    ic.tenant_id
                FROM evolution_proposals ep
                JOIN improvement_candidates ic ON ic.id = ep.improvement_candidate_id
                WHERE ep.id = %s
                FOR UPDATE OF ep
                """,
                (proposal_id,),
            )
            proposal_row = cur.fetchone()
            if not proposal_row:
                raise ProposalNotFoundError("Evolution proposal not found")

            skill_id = proposal_row[3]
            improvement_candidate_id = proposal_row[1]
            proposed_version = proposal_row[5]
            proposed_content = proposal_row[6]
            proposal_status = proposal_row[7]
            tenant_id = proposal_row[13]

            if proposal_status == "rejected":
                raise RejectedProposalError("Rejected proposal cannot be approved")

            cur.execute(
                """
                SELECT id
                FROM skills
                WHERE id = %s
                """,
                (skill_id,),
            )
            if not cur.fetchone():
                raise TargetSkillNotFoundError("Target skill not found")

            cur.execute(
                """
                SELECT id, skill_id, version, status, content, created_at
                FROM skill_versions
                WHERE skill_id = %s AND version = %s
                FOR UPDATE
                """,
                (skill_id, proposed_version),
            )
            existing_version_row = cur.fetchone()
            existing_version = (
                version_row_to_dict(existing_version_row)
                if existing_version_row
                else None
            )
            if proposal_status == "approved" and not existing_version_row:
                raise TargetSkillNotFoundError("Approved skill version not found")
            action = determine_approval_action(
                proposal_status,
                existing_version,
                proposed_content,
            )
            change_summary = get_change_summary(cur, improvement_candidate_id)

            if action == "already_approved":
                proposal = serialize_proposal(proposal_row[:13])
                return proposal, serialize_skill_version(existing_version_row)

            if action == "create":
                cur.execute(
                    """
                    UPDATE skill_versions
                    SET status = 'superseded'
                    WHERE skill_id = %s AND status = 'approved'
                    """,
                    (skill_id,),
                )
                try:
                    cur.execute(
                        """
                        INSERT INTO skill_versions (
                            skill_id,
                            version,
                            status,
                            content,
                            source_evolution_proposal_id,
                            source_improvement_candidate_id,
                            change_summary
                        )
                        VALUES (%s, %s, 'approved', %s, %s, %s, %s)
                        RETURNING id, skill_id, version, status, content, created_at
                        """,
                        (
                            skill_id,
                            proposed_version,
                            proposed_content,
                            proposal_id,
                            improvement_candidate_id,
                            change_summary,
                        ),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise SkillVersionContentConflictError(
                        "Skill version already exists with different content"
                    ) from exc
                skill_version = cur.fetchone()
                skill_version_created = True
            else:
                cur.execute(
                    """
                    UPDATE skill_versions
                    SET status = 'superseded'
                    WHERE skill_id = %s
                        AND status = 'approved'
                        AND id <> %s
                    """,
                    (skill_id, existing_version_row[0]),
                )
                cur.execute(
                    """
                    UPDATE skill_versions
                    SET status = 'approved',
                        source_evolution_proposal_id = %s,
                        source_improvement_candidate_id = %s,
                        change_summary = %s
                    WHERE id = %s
                    RETURNING id, skill_id, version, status, content, created_at
                    """,
                    (
                        proposal_id,
                        improvement_candidate_id,
                        change_summary,
                        existing_version_row[0],
                    ),
                )
                skill_version = cur.fetchone()
                skill_version_created = False

            proposal = approve_locked_proposal(
                cur,
                proposal_id,
                reviewed_by,
                comment,
            )
            insert_event(
                cur,
                tenant_id,
                "EvolutionProposalApproved",
                "evolution_proposal",
                proposal["id"],
                {
                    "target_skill_id": proposal["target_skill_id"],
                    "proposed_version": proposal["proposed_version"],
                    "approved_by": reviewed_by,
                },
                Jsonb,
            )
            if skill_version_created:
                insert_event(
                    cur,
                    None,
                    "SkillVersionCreated",
                    "skill_version",
                    skill_version[0],
                    {
                        "skill_id": str(skill_version[1]),
                        "version": skill_version[2],
                        "status": "approved",
                    },
                    Jsonb,
                )
            insert_event(
                cur,
                None,
                "SkillVersionApproved",
                "skill_version",
                skill_version[0],
                {
                    "skill_id": str(skill_version[1]),
                    "version": skill_version[2],
                },
                Jsonb,
            )

    return proposal, serialize_skill_version(skill_version)


def reject_proposal(proposal_id, reviewed_by, comment, database_url=None):
    database_url = database_url or DATABASE_URL
    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE evolution_proposals
                SET status = 'rejected',
                    approved_by = %s,
                    approval_comment = %s,
                    approved_at = NOW()
                WHERE id = %s AND status = 'draft'
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
                (reviewed_by, comment, proposal_id),
            )
            proposal_row = cur.fetchone()
            if not proposal_row:
                raise ValueError("Draft evolution proposal not found")
            proposal = serialize_proposal(proposal_row)
            conn.commit()

    return proposal


def restore_skill_version(skill_slug, version, database_url=None):
    database_url = database_url or DATABASE_URL
    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sv.id, sv.skill_id
                FROM skill_versions sv
                JOIN skills s ON s.id = sv.skill_id
                WHERE s.slug = %s AND sv.version = %s
                """,
                (skill_slug, version),
            )
            target = cur.fetchone()
            if not target:
                raise ValueError("Skill version not found")

            cur.execute(
                """
                UPDATE skill_versions
                SET status = 'superseded'
                WHERE skill_id = %s AND status = 'approved'
                """,
                (target[1],),
            )
            cur.execute(
                """
                UPDATE skill_versions
                SET status = 'approved'
                WHERE id = %s
                RETURNING id, skill_id, version, status, content, created_at
                """,
                (target[0],),
            )
            restored = serialize_skill_version(cur.fetchone())
            conn.commit()

    return restored


def serialize_skill_version(row):
    return {
        "id": str(row[0]),
        "skill_id": str(row[1]),
        "version": row[2],
        "status": row[3],
        "content": row[4],
        "created_at": row[5].isoformat(),
    }


def version_row_to_dict(row):
    return {
        "id": row[0],
        "skill_id": row[1],
        "version": row[2],
        "status": row[3],
        "content": row[4],
        "created_at": row[5],
    }


def approve_locked_proposal(cur, proposal_id, reviewed_by, comment):
    cur.execute(
        """
        UPDATE evolution_proposals
        SET status = 'approved',
            approved_by = %s,
            approval_comment = %s,
            approved_at = NOW()
        WHERE id = %s
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
        (reviewed_by, comment, proposal_id),
    )
    return serialize_proposal(cur.fetchone())


def get_change_summary(cur, improvement_candidate_id):
    cur.execute(
        """
        SELECT title, body
        FROM improvement_candidates
        WHERE id = %s
        """,
        (improvement_candidate_id,),
    )
    candidate = cur.fetchone()
    if not candidate:
        return "Approved evolution improvement"

    title = candidate[0] or "Approved evolution improvement"
    body = candidate[1] or ""
    summary = title if not body else f"{title}: {body}"
    return summary[:500]


def insert_event(
    cur,
    tenant_id,
    event_type,
    entity_type,
    entity_id,
    payload,
    jsonb_type,
):
    cur.execute(
        """
        INSERT INTO events (tenant_id, event_type, entity_type, entity_id, payload)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            tenant_id,
            event_type,
            entity_type,
            entity_id,
            jsonb_type(payload),
        ),
    )
