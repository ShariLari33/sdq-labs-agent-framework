---
name: Google Ads Performance Analysis
description: Analyse deterministic Google Ads performance summaries from SDQ and produce approval-gated recommendations.
version: 0.1.0
status: approved
capability: performance_analysis
channel: google_ads
---

# Google Ads Performance Analysis

Use this skill when a Paperclip task asks for Google Ads performance analysis for an SDQ partner or tenant.

## Workflow

1. Resolve the tenant slug from the assigned Paperclip task.
2. Resolve the requested period and filters.
3. Call the SDQ performance summary endpoint.
4. Validate that data exists.
5. Review:
   - impressions
   - clicks
   - CTR
   - cost
   - average CPC
   - conversions
   - conversion rate
   - CPA
   - conversion value
   - ROAS
   - deterministic alerts
6. Identify:
   - spend without conversions
   - high-spend/low-contribution campaigns
   - low CTR
   - strongest value-generating campaign
7. Produce structured findings.
8. Produce prioritised recommendations.
9. Mark all external changes as requiring approval.
10. Suggest partner-specific learning where justified.
11. Update the Paperclip task with a concise result.

## SDQ API Access

Use environment variables:

```text
SDQ_API_BASE_URL=http://host.docker.internal:8000
SDQ_INTERNAL_API_TOKEN=
```

Do not hardcode real tokens. On macOS Docker, `host.docker.internal` resolves from containers back to the host.

## Output Structure

- Executive summary
- Period and data source
- Findings
- Recommendations
- Risks and limitations
- Learning suggestions
- Approval required

## Guardrails

- Never invent metrics.
- Never expose raw tenant data.
- Never make external campaign changes.
- Keep partner-specific facts isolated to the partner they came from.
- Treat deterministic SDQ metrics as authoritative.
