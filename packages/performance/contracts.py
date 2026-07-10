from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class PerformanceImportResult:
    import_id: str
    tenant_id: str
    channel: str
    filename: str
    status: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    date_from: str | None
    date_to: str | None
    currency: str | None
    validation_errors: list[dict] = field(default_factory=list)


@dataclass
class GoogleAdsPerformanceRow:
    performance_date: date
    campaign_id: str | None
    campaign_name: str
    campaign_status: str | None
    campaign_type: str | None
    ad_group_id: str | None
    ad_group_name: str | None
    impressions: int
    clicks: int
    cost: Decimal
    conversions: Decimal
    conversion_value: Decimal
    currency: str | None
    raw_data: dict


@dataclass
class PerformanceFilters:
    date_from: str | None = None
    date_to: str | None = None
    campaign_id: str | None = None
    campaign_status: str | None = None


@dataclass
class PerformanceSummary:
    period: dict
    totals: dict
    calculated_metrics: dict
    campaign_breakdown: list[dict]
    alerts: list[dict]
    data_quality: dict
