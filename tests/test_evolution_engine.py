import unittest

from packages.evolution.evaluator import evaluate_candidate
from packages.evolution.proposal_builder import (
    DuplicateImprovementContentError,
    ImprovementCandidateAlreadyAppliedError,
    build_improvement_section,
    draft_skill_content,
    improvement_marker,
    resolve_next_proposal_version,
)
from packages.evolution.versioning import (
    InvalidSemanticVersionError,
    RejectedProposalError,
    SkillVersionContentConflictError,
    build_repair_preview,
    count_improvement_sections,
    determine_approval_action,
    extract_provenance_markers,
    get_latest_skill_version,
    next_minor_version,
    skill_integrity_report,
    validate_skill_base_content,
)


class EvolutionEvaluatorTests(unittest.TestCase):
    def test_no_evidence_recommends_collect_more(self):
        result = evaluate_candidate([], [])

        self.assertEqual(result["recommendation"], "collect_more_evidence")
        self.assertEqual(result["supporting_evidence_count"], 0)

    def test_insufficient_evidence_recommends_collect_more(self):
        result = evaluate_candidate(
            [{"id": "1", "evidence_type": "agent_run", "source_id": "run-1"}],
            [{"verdict": "support", "score": 0.9}],
        )

        self.assertEqual(result["recommendation"], "collect_more_evidence")
        self.assertEqual(result["supporting_evidence_count"], 1)

    def test_supported_candidate_recommends_propose(self):
        result = evaluate_candidate(
            [
                {"id": "1", "evidence_type": "agent_run", "source_id": "run-1"},
                {"id": "2", "evidence_type": "performance_metric", "source_id": "metric-1"},
            ],
            [
                {"verdict": "support", "score": 0.8},
                {"verdict": "support", "score": 0.9},
            ],
        )

        self.assertEqual(result["recommendation"], "propose")
        self.assertGreaterEqual(result["evidence_score"], 0.7)

    def test_high_confidence_reject_wins(self):
        result = evaluate_candidate(
            [
                {"id": "1", "evidence_type": "agent_run", "source_id": "run-1"},
                {"id": "2", "evidence_type": "performance_metric", "source_id": "metric-1"},
            ],
            [
                {"verdict": "support", "score": 0.9},
                {"verdict": "reject", "score": 0.85},
            ],
        )

        self.assertEqual(result["recommendation"], "reject")


class EvolutionProposalBuilderTests(unittest.TestCase):
    def test_mock_style_proposal_appends_evidence_backed_section(self):
        content = draft_skill_content(
            "# Skill\n\nExisting requirements.",
            {
                "id": "candidate-1",
                "title": "Improve wasted spend handling",
                "body": "Add clearer wasted spend review steps.",
            },
            [
                {
                    "evidence_type": "agent_run",
                    "description": "The run produced reusable wasted spend guidance.",
                }
            ],
            [
                {
                    "verdict": "support",
                    "score": 0.8,
                    "rationale": "Evidence is strong enough.",
                }
            ],
        )

        self.assertIn("Existing requirements.", content)
        self.assertIn("## Evidence-backed improvement", content)
        self.assertIn("Human approval remains required", content)
        self.assertIn("<!-- sdq-improvement-candidate:candidate-1 -->", content)

    def test_proposal_content_contains_one_marker_and_one_section(self):
        candidate = {
            "id": "candidate-1",
            "title": "Improve wasted spend handling",
            "body": "Add clearer wasted spend review steps.",
        }

        content = draft_skill_content("# Skill", candidate, [], [])

        self.assertEqual(content.count(improvement_marker("candidate-1")), 1)
        self.assertEqual(content.count("## Evidence-backed improvement"), 1)

    def test_same_candidate_marker_cannot_be_appended_twice(self):
        candidate = {
            "id": "candidate-1",
            "title": "Improve wasted spend handling",
            "body": "Add clearer wasted spend review steps.",
        }
        current_content = "\n\n".join(
            ["# Skill", build_improvement_section(candidate, [], [])]
        )

        with self.assertRaises(ImprovementCandidateAlreadyAppliedError):
            draft_skill_content(current_content, candidate, [], [])

    def test_exact_duplicate_improvement_text_is_conflict(self):
        candidate = {
            "id": "candidate-1",
            "title": "Improve wasted spend handling",
            "body": "Add clearer wasted spend review steps.",
        }
        section = build_improvement_section(candidate, [], [])
        current_content = section.replace(improvement_marker("candidate-1"), "")

        with self.assertRaises(DuplicateImprovementContentError):
            draft_skill_content(current_content, candidate, [], [])

    def test_resolve_next_proposal_version_uses_latest_existing_version(self):
        cursor = FakeVersionCursor(["0.1.0", "0.2.0"])

        version = resolve_next_proposal_version(cursor, "skill-1", "0.2.0")

        self.assertEqual(version, "0.3.0")

    def test_existing_version_is_skipped_safely(self):
        cursor = FakeVersionCursor(["0.1.0", "0.2.0", "0.3.0"])

        version = resolve_next_proposal_version(cursor, "skill-1", "0.2.0")

        self.assertEqual(version, "0.4.0")


class EvolutionVersioningTests(unittest.TestCase):
    def test_polluted_approved_version_is_detected(self):
        content = "\n\n".join(
            [
                "# Skill",
                "Human approval is required.",
                "## Evidence-backed improvement\nA",
                "## Evidence-backed improvement\nA",
            ]
        )

        report = skill_integrity_report(content)

        self.assertFalse(report["healthy"])
        self.assertEqual(report["improvement_section_count"], 2)

    def test_duplicate_provenance_markers_detected(self):
        content = "\n".join(
            [
                "# Skill",
                "Human approval is required.",
                "<!-- sdq-improvement-candidate:candidate-1 -->",
                "<!-- sdq-improvement-candidate:candidate-1 -->",
            ]
        )

        report = skill_integrity_report(content)

        self.assertEqual(report["duplicate_provenance_markers"], ["candidate-1"])

    def test_repair_preview_deduplicates_identical_sections(self):
        block = "\n".join(
            [
                "## Evidence-backed improvement",
                "Candidate: Improve pacing",
                "Human approval remains required before any external change.",
            ]
        )
        content = "\n\n".join(["# Skill\n\nHuman approval is required.", block, block])

        preview = build_repair_preview(content)

        self.assertEqual(preview["before"]["improvement_section_count"], 2)
        self.assertEqual(preview["after"]["improvement_section_count"], 1)
        self.assertIn("Human approval is required", preview["after"]["content"])

    def test_human_approval_rule_is_required(self):
        with self.assertRaises(ValueError):
            validate_skill_base_content("# Skill")

    def test_extract_provenance_markers(self):
        content = "<!-- sdq-improvement-candidate:candidate-1 -->"

        self.assertEqual(extract_provenance_markers(content), ["candidate-1"])

    def test_count_improvement_sections(self):
        content = "## Evidence-backed improvement\nA\n## Evidence-backed improvement\nB"

        self.assertEqual(count_improvement_sections(content), 2)

    def test_next_minor_version_increments_minor(self):
        self.assertEqual(next_minor_version("0.1.0"), "0.2.0")
        self.assertEqual(next_minor_version("0.2.0"), "0.3.0")
        self.assertEqual(next_minor_version("1.8.0"), "1.9.0")
        self.assertEqual(next_minor_version("2.4.7"), "2.5.0")

    def test_invalid_semantic_version_raises_domain_error(self):
        with self.assertRaises(InvalidSemanticVersionError):
            next_minor_version("0.1")

    def test_latest_skill_version_is_determined_numerically(self):
        conn = FakeVersionConnection(
            [
                ("id-1", "skill-1", "0.9.0", "superseded", "old", None),
                ("id-2", "skill-1", "0.10.0", "approved", "new", None),
                ("id-3", "skill-1", "0.2.0", "superseded", "older", None),
            ]
        )

        latest = get_latest_skill_version(conn, "skill-1")

        self.assertEqual(latest[2], "0.10.0")

    def test_approve_creates_new_version_when_version_is_missing(self):
        action = determine_approval_action("draft", None, "new content")

        self.assertEqual(action, "create")

    def test_approve_reuses_matching_draft_version(self):
        action = determine_approval_action(
            "draft",
            {"status": "draft", "content": "new content"},
            "new content",
        )

        self.assertEqual(action, "reuse_existing")

    def test_approve_matching_approved_version_is_idempotent(self):
        action = determine_approval_action(
            "approved",
            {"status": "approved", "content": "new content"},
            "new content",
        )

        self.assertEqual(action, "already_approved")

    def test_approve_existing_different_content_is_conflict(self):
        with self.assertRaises(SkillVersionContentConflictError):
            determine_approval_action(
                "draft",
                {"status": "draft", "content": "old content"},
                "new content",
            )

    def test_approving_rejected_proposal_is_conflict(self):
        with self.assertRaises(RejectedProposalError):
            determine_approval_action("rejected", None, "new content")


class FakeVersionCursor:
    def __init__(self, versions):
        self.versions = versions
        self.params = None

    def execute(self, query, params):
        self.params = params

    def fetchall(self):
        return [(version,) for version in self.versions]


class FakeVersionConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return FakeLatestVersionCursor(self.rows)


class FakeLatestVersionCursor:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.params = params

    def fetchall(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
