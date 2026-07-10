import json
import time

from packages.ai.contracts import LLMCost, LLMRequest, LLMResult, LLMUsage
from packages.ai.providers.base import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, request: LLMRequest) -> LLMResult:
        started = time.monotonic()
        payload = (
            performance_analysis_response(request.metadata["performance_summary"])
            if request.metadata.get("task_type") == "performance_analysis"
            and request.metadata.get("performance_summary")
            else generic_response()
        )
        text = json.dumps(payload)
        latency_ms = int((time.monotonic() - started) * 1000)

        return LLMResult(
            provider=self.provider_name,
            model=request.model,
            text=text,
            usage=LLMUsage(input_tokens=0, output_tokens=0, total_tokens=0),
            cost=LLMCost(estimated_amount=0),
            latency_ms=latency_ms,
            provider_response_id=None,
            raw_metadata={"mock": True},
        )

    def health_check(self) -> dict:
        return {"configured": True, "healthy": True}


def generic_response():
    return {
        "summary": "Mock provider completed the analysis.",
        "findings": ["Mock finding: performance data was reviewed."],
        "recommendations": ["Mock recommendation: review high-spend areas first."],
        "learning_candidates": [
            {
                "title": "Mock reusable performance insight",
                "body": "Prioritize wasted spend and budget pacing in future analyses.",
            }
        ],
        "approval_required": True,
    }


def performance_analysis_response(summary):
    findings = []
    recommendations = []
    campaigns = summary.get("campaign_breakdown", [])
    for campaign in campaigns:
        metrics = campaign.get("metrics", {})
        totals = campaign.get("totals", {})
        evidence = campaign_evidence(totals, metrics)
        if totals.get("cost", 0) >= 100 and totals.get("conversions", 0) == 0:
            add_finding(
                findings,
                recommendations,
                campaign,
                "Campaign is spending without generating conversions.",
                "Pause, reduce budget or inspect search terms.",
                "high",
                evidence,
            )
        if (
            (campaign.get("spend_share") or 0) >= 0.30
            and (campaign.get("conversion_share") or 0) < 0.10
        ):
            add_finding(
                findings,
                recommendations,
                campaign,
                "Campaign consumes a high share of spend but contributes little conversion volume.",
                "Investigate targeting, bids and search terms.",
                "high",
                evidence,
            )
        if totals.get("impressions", 0) >= 1000 and (metrics.get("ctr") or 0) < 0.01:
            add_finding(
                findings,
                recommendations,
                campaign,
                "Campaign CTR is below the configured threshold.",
                "Improve ads, targeting or keyword relevance.",
                "medium",
                evidence,
            )

    strongest = strongest_campaign(campaigns)
    if strongest:
        add_finding(
            findings,
            recommendations,
            strongest,
            "Campaign is one of the strongest value-generating campaigns.",
            "Consider controlled budget expansion.",
            "medium",
            campaign_evidence(strongest.get("totals", {}), strongest.get("metrics", {})),
        )

    if not findings and strongest:
        add_finding(
            findings,
            recommendations,
            strongest,
            "Campaign is currently the strongest campaign in the supplied summary.",
            "Continue monitoring before making larger budget changes.",
            "low",
            campaign_evidence(strongest.get("totals", {}), strongest.get("metrics", {})),
        )

    return {
        "summary": (
            "Deterministic Google Ads performance summary reviewed for "
            f"{summary.get('period', {}).get('date_from')} to {summary.get('period', {}).get('date_to')}."
        ),
        "findings": findings,
        "recommendations": recommendations,
        "learning_candidates": [
            {
                "title": "Reusable Google Ads performance review pattern",
                "body": "Prioritize campaigns with spend without conversions, low CTR, or weak conversion share before recommending budget expansion.",
            }
        ],
        "approval_required": True,
    }


def add_finding(findings, recommendations, campaign, observation, action, priority, evidence):
    campaign_name = campaign.get("campaign_name")
    if any(item.get("campaign") == campaign_name and item.get("observation") == observation for item in findings):
        return
    findings.append(
        {
            "campaign": campaign_name,
            "observation": observation,
            "evidence": evidence,
        }
    )
    recommendations.append(
        {
            "campaign": campaign_name,
            "action": action,
            "reason": observation,
            "priority": priority,
            "requires_external_change": True,
        }
    )


def campaign_evidence(totals, metrics):
    return [
        f"Cost: {format_number(totals.get('cost'))}",
        f"Conversions: {format_number(totals.get('conversions'))}",
        f"CPA: {format_number(metrics.get('cost_per_conversion'))}",
        f"ROAS: {format_number(metrics.get('roas'))}",
    ]


def strongest_campaign(campaigns):
    candidates = [
        campaign for campaign in campaigns
        if campaign.get("metrics", {}).get("roas") is not None
    ]
    if not candidates:
        return campaigns[0] if campaigns else None
    return max(candidates, key=lambda campaign: campaign["metrics"]["roas"])


def format_number(value):
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"
