from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from packages.performance.contracts import GoogleAdsPerformanceRow

CANONICAL_FIELDS = [
    "date",
    "campaign_id",
    "campaign_name",
    "campaign_status",
    "campaign_type",
    "ad_group_id",
    "ad_group_name",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "conversion_value",
    "currency",
]

HEADER_ALIASES = {
    "day": "date",
    "date": "date",
    "campaign id": "campaign_id",
    "campaign": "campaign_name",
    "campaign name": "campaign_name",
    "campaign status": "campaign_status",
    "campaign type": "campaign_type",
    "ad group id": "ad_group_id",
    "ad group": "ad_group_name",
    "ad group name": "ad_group_name",
    "impr.": "impressions",
    "impressions": "impressions",
    "clicks": "clicks",
    "cost": "cost",
    "cost (eur)": "cost",
    "cost (usd)": "cost",
    "conversions": "conversions",
    "conv. value": "conversion_value",
    "conversion value": "conversion_value",
    "currency": "currency",
}


class CsvValidationError(ValueError):
    pass


def decode_csv(file_bytes: bytes) -> str:
    if b"\x00" in file_bytes:
        raise CsvValidationError("File appears to be binary")
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV must be UTF-8 text") from exc


def normalize_header(header: str) -> str:
    cleaned = " ".join((header or "").strip().split()).lower()
    return HEADER_ALIASES.get(cleaned, cleaned.replace(" ", "_"))


def read_csv_rows(file_bytes: bytes) -> tuple[list[dict], dict]:
    text = decode_csv(file_bytes)
    if not text.strip():
        raise CsvValidationError("CSV is empty")

    sample = text[:2048]
    dialect = csv.Sniffer().sniff(sample) if "," in sample or ";" in sample else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise CsvValidationError("CSV header is missing")

    mapping = {header: normalize_header(header) for header in reader.fieldnames}
    rows = []
    for row in reader:
        rows.append({mapping[key]: value for key, value in row.items() if key is not None})
    if not rows:
        raise CsvValidationError("CSV contains no data rows")
    return rows, mapping


def normalize_google_ads_row(row: dict) -> GoogleAdsPerformanceRow:
    campaign_name = clean_text(row.get("campaign_name"))
    if not campaign_name:
        raise CsvValidationError("campaign_name is required")

    performance_date = parse_date(row.get("date"))
    impressions = parse_int(row.get("impressions"), "impressions")
    clicks = parse_int(row.get("clicks"), "clicks")
    cost = parse_decimal(row.get("cost"), "cost")
    conversions = parse_decimal(row.get("conversions"), "conversions")
    conversion_value = parse_decimal(row.get("conversion_value"), "conversion_value")

    if clicks > impressions:
        raise CsvValidationError("clicks may not exceed impressions")

    return GoogleAdsPerformanceRow(
        performance_date=performance_date,
        campaign_id=clean_text(row.get("campaign_id")),
        campaign_name=campaign_name,
        campaign_status=clean_text(row.get("campaign_status")),
        campaign_type=clean_text(row.get("campaign_type")),
        ad_group_id=clean_text(row.get("ad_group_id")),
        ad_group_name=clean_text(row.get("ad_group_name")),
        impressions=impressions,
        clicks=clicks,
        cost=cost,
        conversions=conversions,
        conversion_value=conversion_value,
        currency=clean_text(row.get("currency")),
        raw_data={key: safe_cell(value) for key, value in row.items()},
    )


def safe_cell(value):
    text = clean_text(value)
    return text if text is not None else ""


def clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_date(value):
    text = clean_text(value)
    if not text:
        raise CsvValidationError("date is required")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise CsvValidationError("date is invalid")


def parse_int(value, field):
    number = parse_decimal(value, field)
    if number != number.to_integral_value():
        raise CsvValidationError(f"{field} must be a whole number")
    return int(number)


def parse_decimal(value, field):
    text = clean_text(value) or "0"
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise CsvValidationError(f"{field} is invalid") from exc
    if number < 0:
        raise CsvValidationError(f"{field} may not be negative")
    return number
