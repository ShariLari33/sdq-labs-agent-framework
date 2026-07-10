from __future__ import annotations

from packages.performance.analytics import calculate_google_ads_summary
from packages.performance.contracts import PerformanceFilters
from packages.performance.repository import get_google_ads_summary_data


def read_google_ads_performance(conn, tenant_id, filters):
    performance_filters = PerformanceFilters(**(filters or {}))
    rows = get_google_ads_summary_data(conn, tenant_id, performance_filters)
    return calculate_google_ads_summary(rows, performance_filters)
