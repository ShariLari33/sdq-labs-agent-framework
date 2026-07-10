# Performance Data

The Google Ads Performance Data Layer stores tenant-scoped CSV imports and exposes deterministic summaries for workers and LLM analysis.

## Canonical CSV

Required columns:

`date,campaign_id,campaign_name,campaign_status,campaign_type,ad_group_id,ad_group_name,impressions,clicks,cost,conversions,conversion_value,currency`

Supported aliases include `Day`, `Date`, `Campaign ID`, `Campaign`, `Campaign status`, `Campaign type`, `Ad group ID`, `Ad group`, `Impr.`, `Impressions`, `Clicks`, `Cost`, `Cost (EUR)`, `Cost (USD)`, `Conversions`, `Conv. value`, `Conversion value`, and `Currency`.

## Upload Flow

Upload CSV data per tenant:

```bash
curl -s -X POST http://localhost:8000/performance-data/demo-partner-a/google-ads/import \
  -F "created_by=sharif" \
  -F "file=@data/samples/google_ads_performance_sample.csv"
```

The API validates rows, stores valid tenant-scoped rows, records up to 100 validation errors, and emits import events.

## Tenant Isolation

Every import and performance row includes `tenant_id`. Repository queries always require `tenant_id`, and import ids are resolved within tenant scope.

## Calculated Metrics

CTR, average CPC, conversion rate, cost per conversion, and ROAS are calculated from source metrics at read time. They are not stored as source-of-truth columns.

## Alert Thresholds

Initial deterministic alert thresholds:

- Spend without conversions: cost >= 100 and conversions = 0
- Low CTR: impressions >= 1000 and CTR < 0.01
- High spend with low conversion share: spend share >= 0.30 and conversion share < 0.10

These are deliberately simple constants in `packages/performance/analytics.py`.

## Summaries

```bash
curl -s "http://localhost:8000/performance-data/demo-partner-a/google-ads/summary?date_from=2026-06-01&date_to=2026-06-04"
```

Summaries include totals, calculated metrics, campaign breakdown, alerts, and data quality. They do not include raw CSV rows.

## Future Google Ads API

The CSV importer is the MVP ingestion path. A future Google Ads API connector can write into the same canonical tables.

## Why Deterministic Analytics First

Workers and LLMs receive deterministic summaries instead of raw rows. This keeps metric calculation consistent, auditable, tenant-scoped, and cheaper to reason about. The LLM may explain and recommend, but it must not invent or recalculate metrics.
