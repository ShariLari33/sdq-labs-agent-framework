from __future__ import annotations


def evaluate_candidate(evidence: list[dict], evaluations: list[dict]) -> dict:
    reasons = []

    if not evidence:
        return {
            "evidence_score": 0,
            "supporting_evidence_count": 0,
            "recommendation": "collect_more_evidence",
            "reasons": ["No evidence has been collected."],
        }

    independent_count = _independent_evidence_count(evidence)
    if independent_count < 2:
        return {
            "evidence_score": _average_support_score(evaluations),
            "supporting_evidence_count": independent_count,
            "recommendation": "collect_more_evidence",
            "reasons": ["Fewer than 2 independent evidence items."],
        }

    for evaluation in evaluations:
        if (
            evaluation.get("verdict") == "reject"
            and (evaluation.get("score") or 0) >= 0.8
        ):
            return {
                "evidence_score": _average_support_score(evaluations),
                "supporting_evidence_count": independent_count,
                "recommendation": "reject",
                "reasons": ["A high-confidence rejection evaluation exists."],
            }

    evidence_score = _average_support_score(evaluations)
    if independent_count >= 2 and evidence_score >= 0.7:
        reasons.append("At least 2 independent evidence items support this candidate.")
        reasons.append("Average supporting evaluation score is at least 0.7.")
        return {
            "evidence_score": evidence_score,
            "supporting_evidence_count": independent_count,
            "recommendation": "propose",
            "reasons": reasons,
        }

    return {
        "evidence_score": evidence_score,
        "supporting_evidence_count": independent_count,
        "recommendation": "collect_more_evidence",
        "reasons": ["Evidence exists but support is not strong enough yet."],
    }


def _independent_evidence_count(evidence):
    return len(
        {
            (
                item.get("evidence_type"),
                item.get("source_id") or item.get("id"),
            )
            for item in evidence
        }
    )


def _average_support_score(evaluations):
    scores = [
        item.get("score")
        for item in evaluations
        if item.get("verdict") == "support" and item.get("score") is not None
    ]
    if not scores:
        return 0
    return sum(float(score) for score in scores) / len(scores)
