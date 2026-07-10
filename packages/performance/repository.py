from __future__ import annotations

from packages.performance.contracts import PerformanceFilters


def get_imports_for_tenant(conn, tenant_id, channel=None):
    params = [tenant_id]
    channel_filter = ""
    if channel:
        channel_filter = "AND channel = %s"
        params.append(channel)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, tenant_id, channel, filename, status, row_count,
                   valid_row_count, invalid_row_count, date_from, date_to,
                   currency, validation_errors, created_by, created_at, completed_at
            FROM performance_imports
            WHERE tenant_id = %s {channel_filter}
            ORDER BY created_at DESC
            """,
            tuple(params),
        )
        return [serialize_import(row) for row in cur.fetchall()]


def get_import_by_id(conn, tenant_id, import_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, channel, filename, status, row_count,
                   valid_row_count, invalid_row_count, date_from, date_to,
                   currency, validation_errors, created_by, created_at, completed_at
            FROM performance_imports
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, import_id),
        )
        row = cur.fetchone()
    return serialize_import(row) if row else None


def get_google_ads_rows(conn, tenant_id, filters: PerformanceFilters | None = None):
    filters = filters or PerformanceFilters()
    where, params = build_row_filters(tenant_id, filters)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT import_id, performance_date, campaign_id, campaign_name,
                   campaign_status, campaign_type, impressions, clicks, cost,
                   conversions, conversion_value, currency
            FROM google_ads_performance_rows
            WHERE {where}
            ORDER BY performance_date ASC, campaign_name ASC
            LIMIT 5000
            """,
            tuple(params),
        )
        return [serialize_row(row) for row in cur.fetchall()]


def get_google_ads_summary_data(conn, tenant_id, filters: PerformanceFilters | None = None):
    return get_google_ads_rows(conn, tenant_id, filters)


def build_row_filters(tenant_id, filters):
    clauses = ["tenant_id = %s"]
    params = [tenant_id]
    if filters.date_from:
        clauses.append("performance_date >= %s")
        params.append(filters.date_from)
    if filters.date_to:
        clauses.append("performance_date <= %s")
        params.append(filters.date_to)
    if filters.campaign_id:
        clauses.append("campaign_id = %s")
        params.append(filters.campaign_id)
    if filters.campaign_status:
        clauses.append("campaign_status = %s")
        params.append(filters.campaign_status)
    return " AND ".join(clauses), params


def serialize_import(row):
    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "channel": row[2],
        "filename": row[3],
        "status": row[4],
        "row_count": row[5],
        "valid_row_count": row[6],
        "invalid_row_count": row[7],
        "date_from": row[8].isoformat() if row[8] else None,
        "date_to": row[9].isoformat() if row[9] else None,
        "currency": row[10],
        "validation_errors": row[11],
        "created_by": row[12],
        "created_at": row[13].isoformat(),
        "completed_at": row[14].isoformat() if row[14] else None,
    }


def serialize_row(row):
    return {
        "import_id": str(row[0]),
        "performance_date": row[1].isoformat(),
        "campaign_id": row[2],
        "campaign_name": row[3],
        "campaign_status": row[4],
        "campaign_type": row[5],
        "impressions": int(row[6]),
        "clicks": int(row[7]),
        "cost": float(row[8]),
        "conversions": float(row[9]),
        "conversion_value": float(row[10]),
        "currency": row[11],
    }
