import json


def normalize_llm_output(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return {
            "summary": text or "",
            "findings": [],
            "recommendations": [],
            "learning_candidates": [],
            "approval_required": True,
        }

    return {
        "summary": parsed.get("summary") or "",
        "findings": _as_list(parsed.get("findings")),
        "recommendations": _as_list(parsed.get("recommendations")),
        "learning_candidates": _as_list(
            parsed.get("learning_candidates")
            or parsed.get("learning_candidate")
        ),
        "approval_required": bool(parsed.get("approval_required", True)),
    }


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
