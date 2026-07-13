# SDQ Labs Growth Sandbox

This package contains a fully synthetic company and Google Ads dataset for end-to-end SDQ Labs Agent Framework testing before a real customer or live advertising account exists.

All data is fictional. Do not connect these scripts to real ad accounts, real credentials, or production tenants.

## Tenant

- Name: SDQ Labs Growth Sandbox
- Slug: `sdq-labs-growth-sandbox`
- Currency: EUR
- Primary channel: Google Ads

## Demo Flow

Start the local API stack first:

```bash
docker compose up -d --build
```

Bootstrap the tenant and load the baseline data:

```bash
sandbox/sdq-labs-growth/scripts/load-baseline.sh
```

Run the complete synthetic demo:

```bash
sandbox/sdq-labs-growth/scripts/run-demo-flow.sh
```

Verify the current sandbox state:

```bash
sandbox/sdq-labs-growth/scripts/verify-demo-flow.sh
```

Reset only this sandbox tenant's task/import/run/demo data:

```bash
sandbox/sdq-labs-growth/scripts/reset-sandbox-data.sh
```

## Periods

- Baseline: Broad Growth Experiments spends heavily with zero conversions.
- Follow-up: Broad spend is reduced and Non Brand improves after search-term cleanup.
- Validation: Improvement largely persists and Broad remains controlled.

See `expected-results/` for approximate outcomes and expected recommendations.

## Paperclip Manual Steps

Paperclip/Hermes registration is not required to import data or run the SDQ API mock engine. If Paperclip is configured:

1. Open Paperclip at `http://localhost:3100`.
2. Create a company named `SDQ Labs Growth Sandbox`.
3. Assign the registered Hermes Gateway agent or bind it to the Google Ads Performance Analyst workflow.
4. Create or mirror the baseline task from `tasks/baseline-analysis.json`.
5. Review the output, then approve or reject the pending approval.
6. Load follow-up data and run `tasks/followup-analysis.json`.
7. Compare follow-up output against the expected lower CPA and improved ROAS.

