from __future__ import annotations

import hashlib
import os

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from packages.performance.contracts import PerformanceImportResult
from packages.performance.normalizer import (
    CsvValidationError,
    normalize_google_ads_row,
    read_csv_rows,
)

CHANNEL = "google_ads"


class DuplicateImportError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


def import_google_ads_csv(conn, tenant_id, filename, file_bytes, created_by=None):
    safe_filename = sanitize_filename(filename)
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    rows, mapping = read_csv_rows(file_bytes)

    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO performance_imports (
                    tenant_id, channel, filename, file_sha256, status, mapping, created_by
                )
                VALUES (%s, %s, %s, %s, 'processing', %s, %s)
                RETURNING id
                """,
                (
                    tenant_id,
                    CHANNEL,
                    safe_filename,
                    file_sha256,
                    Jsonb(mapping),
                    created_by,
                ),
            )
        except UniqueViolation as exc:
            conn.rollback()
            raise DuplicateImportError("Duplicate import for tenant and channel") from exc
        import_id = cur.fetchone()[0]

        valid_rows = []
        validation_errors = []
        currencies = set()
        for index, row in enumerate(rows, start=2):
            try:
                normalized = normalize_google_ads_row(row)
                valid_rows.append(normalized)
                if normalized.currency:
                    currencies.add(normalized.currency)
            except CsvValidationError as exc:
                if len(validation_errors) < 100:
                    validation_errors.append({"row": index, "error": str(exc)})

        if len(currencies) > 1:
            validation_errors.append({"row": None, "error": "Mixed currencies are not supported"})
            valid_rows = []

        for row in valid_rows:
            cur.execute(
                """
                INSERT INTO google_ads_performance_rows (
                    tenant_id, import_id, performance_date, campaign_id, campaign_name,
                    campaign_status, campaign_type, ad_group_id, ad_group_name,
                    impressions, clicks, cost, conversions, conversion_value,
                    currency, raw_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    import_id,
                    row.performance_date,
                    row.campaign_id,
                    row.campaign_name,
                    row.campaign_status,
                    row.campaign_type,
                    row.ad_group_id,
                    row.ad_group_name,
                    row.impressions,
                    row.clicks,
                    row.cost,
                    row.conversions,
                    row.conversion_value,
                    row.currency,
                    Jsonb(row.raw_data),
                ),
            )

        status = import_status(len(rows), len(valid_rows))
        dates = [row.performance_date for row in valid_rows]
        currency = next(iter(currencies)) if len(currencies) == 1 else None
        cur.execute(
            """
            UPDATE performance_imports
            SET status = %s,
                row_count = %s,
                valid_row_count = %s,
                invalid_row_count = %s,
                date_from = %s,
                date_to = %s,
                currency = %s,
                validation_errors = %s,
                completed_at = NOW()
            WHERE id = %s AND tenant_id = %s
            RETURNING id, tenant_id, channel, filename, status, row_count,
                      valid_row_count, invalid_row_count, date_from, date_to,
                      currency, validation_errors
            """,
            (
                status,
                len(rows),
                len(valid_rows),
                len(rows) - len(valid_rows),
                min(dates) if dates else None,
                max(dates) if dates else None,
                currency,
                Jsonb(validation_errors[:100]),
                import_id,
                tenant_id,
            ),
        )
        result = cur.fetchone()
        conn.commit()

    return serialize_import_result(result)


def import_status(row_count, valid_row_count):
    if valid_row_count == 0:
        return "failed"
    if valid_row_count < row_count:
        return "completed_with_errors"
    return "completed"


def sanitize_filename(filename):
    return os.path.basename(filename or "upload.csv").replace("\x00", "")[:255]


def serialize_import_result(row):
    return PerformanceImportResult(
        import_id=str(row[0]),
        tenant_id=str(row[1]),
        channel=row[2],
        filename=row[3],
        status=row[4],
        row_count=row[5],
        valid_row_count=row[6],
        invalid_row_count=row[7],
        date_from=row[8].isoformat() if row[8] else None,
        date_to=row[9].isoformat() if row[9] else None,
        currency=row[10],
        validation_errors=row[11],
    )
