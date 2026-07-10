from __future__ import annotations

from collections import defaultdict
from datetime import date

SPEND_WITHOUT_CONVERSIONS_COST = 100
LOW_CTR_MIN_IMPRESSIONS = 1000
LOW_CTR_THRESHOLD = 0.01
HIGH_SPEND_SHARE = 0.30
LOW_CONVERSION_SHARE = 0.10


class NoPerformanceDataError(ValueError):
    pass


def calculate_google_ads_summary(rows, filters=None):
    if not rows:
        raise NoPerformanceDataError("No matching performance rows found")

    totals = empty_totals()
    campaign_totals = defaultdict(empty_campaign)
    import_ids = set()
    dates = []

    for row in rows:
        import_ids.add(row["import_id"])
        row_date = date.fromisoformat(row["performance_date"])
        dates.append(row_date)
        add_totals(totals, row)
        key = row["campaign_id"] or row["campaign_name"]
        campaign = campaign_totals[key]
        campaign["campaign_id"] = row["campaign_id"]
        campaign["campaign_name"] = row["campaign_name"]
        campaign["status"] = row["campaign_status"]
        campaign["type"] = row["campaign_type"]
        add_totals(campaign["totals"], row)

    calculated_metrics = calculate_metrics(totals)
    breakdown = []
    for campaign in campaign_totals.values():
        campaign["metrics"] = calculate_metrics(campaign["totals"])
        campaign["spend_share"] = safe_div(campaign["totals"]["cost"], totals["cost"])
        campaign["conversion_share"] = safe_div(
            campaign["totals"]["conversions"],
            totals["conversions"],
        )
        breakdown.append(campaign)

    breakdown.sort(key=lambda item: item["totals"]["cost"], reverse=True)
    alerts = build_alerts(breakdown)
    data_quality = {
        "row_count": len(rows),
        "import_ids": sorted(import_ids),
        "warnings": [alert for alert in alerts if alert["type"] == "data_quality_warning"],
    }
    return {
        "period": {
            "date_from": min(dates).isoformat(),
            "date_to": max(dates).isoformat(),
            "days": (max(dates) - min(dates)).days + 1,
        },
        "totals": round_totals(totals),
        "calculated_metrics": calculated_metrics,
        "campaign_breakdown": breakdown,
        "alerts": alerts,
        "data_quality": data_quality,
    }


def empty_totals():
    return {
        "impressions": 0,
        "clicks": 0,
        "cost": 0.0,
        "conversions": 0.0,
        "conversion_value": 0.0,
    }


def empty_campaign():
    return {
        "campaign_id": None,
        "campaign_name": None,
        "status": None,
        "type": None,
        "totals": empty_totals(),
    }


def add_totals(totals, row):
    totals["impressions"] += int(row["impressions"])
    totals["clicks"] += int(row["clicks"])
    totals["cost"] += float(row["cost"])
    totals["conversions"] += float(row["conversions"])
    totals["conversion_value"] += float(row["conversion_value"])


def calculate_metrics(totals):
    return {
        "ctr": safe_div(totals["clicks"], totals["impressions"]),
        "average_cpc": safe_div(totals["cost"], totals["clicks"]),
        "conversion_rate": safe_div(totals["conversions"], totals["clicks"]),
        "cost_per_conversion": safe_div(totals["cost"], totals["conversions"]),
        "roas": safe_div(totals["conversion_value"], totals["cost"]),
    }


def safe_div(numerator, denominator):
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 6)


def round_totals(totals):
    return {
        "impressions": totals["impressions"],
        "clicks": totals["clicks"],
        "cost": round(totals["cost"], 6),
        "conversions": round(totals["conversions"], 6),
        "conversion_value": round(totals["conversion_value"], 6),
    }


def build_alerts(campaigns):
    alerts = []
    for campaign in campaigns:
        totals = campaign["totals"]
        metrics = campaign["metrics"]
        if totals["cost"] >= SPEND_WITHOUT_CONVERSIONS_COST and totals["conversions"] == 0:
            alerts.append(alert("spend_without_conversions", campaign))
        if totals["impressions"] >= LOW_CTR_MIN_IMPRESSIONS and (metrics["ctr"] or 0) < LOW_CTR_THRESHOLD:
            alerts.append(alert("low_ctr", campaign))
        if campaign["spend_share"] is not None and campaign["conversion_share"] is not None:
            if campaign["spend_share"] >= HIGH_SPEND_SHARE and campaign["conversion_share"] < LOW_CONVERSION_SHARE:
                alerts.append(alert("high_spend_low_conversion_share", campaign))
        if totals["conversions"] > 0 and totals["conversion_value"] == 0:
            alerts.append(alert("missing_conversion_value", campaign))
    return alerts


def alert(alert_type, campaign):
    return {
        "type": alert_type,
        "campaign_id": campaign["campaign_id"],
        "campaign_name": campaign["campaign_name"],
        "message": f"{alert_type} detected for {campaign['campaign_name']}",
    }
