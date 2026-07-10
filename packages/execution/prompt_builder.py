from __future__ import annotations

import json


def build_prompts(execution_package) -> tuple[str, str]:
    capability = execution_package.get("capability", {})
    skills = execution_package.get("skills", [])
    memory = execution_package.get("memory", [])
    permissions = execution_package.get("permissions", [])
    task = execution_package.get("task", {})
    context = execution_package.get("context", {})

    partner_memory = [item for item in memory if item.get("tenant_id")]
    global_memory = [item for item in memory if not item.get("tenant_id")]

    performance_summary = context.get("performance_summary")
    performance_instructions = []
    if performance_summary:
        performance_instructions = [
            "Performance analysis rules:",
            "- Deterministic metrics supplied in context are authoritative.",
            "- Do not recalculate, invent, or extrapolate metrics.",
            "- Cite campaign names and supplied metrics in findings.",
            "- Distinguish observation from recommendation.",
            "- No external change is allowed without approval.",
        ]

    system_prompt = "\n\n".join(
        [
            "You are executing a capability-based marketing operations task.",
            f"Capability: {capability.get('name')}\nDescription: {capability.get('description')}",
            "Approved skills:\n" + _format_skills(skills),
            "Partner memory (context, not guaranteed truth):\n" + _format_memory(partner_memory),
            "Global memory (context, not guaranteed truth):\n" + _format_memory(global_memory),
            "Permissions:\n" + "\n".join(f"- {item}" for item in permissions),
            "\n".join(performance_instructions),
            "Approval rules: external changes require approval. Do not claim changes were made.",
            (
                "Return JSON with keys: summary, findings, recommendations, "
                "learning_candidates, approval_required."
            ),
        ]
    )

    user_prompt = "\n\n".join(
        [
            f"Task title: {task.get('title')}",
            "Task input:\n" + json.dumps(task.get("input", {}), indent=2, sort_keys=True),
            "Relevant context:\n" + json.dumps(context, indent=2, sort_keys=True),
        ]
    )

    return system_prompt, user_prompt


def _format_skills(skills):
    if not skills:
        return "- None"
    return "\n\n".join(
        f"Skill: {skill.get('name')} ({skill.get('slug')} v{skill.get('version')})\n"
        f"{skill.get('content', '')}"
        for skill in skills
    )


def _format_memory(memory_items):
    if not memory_items:
        return "- None"
    return "\n".join(
        f"- {item.get('title')}: {item.get('body')}"
        for item in memory_items
    )
