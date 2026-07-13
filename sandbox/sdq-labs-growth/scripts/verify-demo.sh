#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PAPERCLIP_URL="${PAPERCLIP_URL:-http://localhost:3100}"
HERMES_GATEWAY_URL="${HERMES_GATEWAY_URL:-http://localhost:8642}"
TENANT_SLUG="sdq-labs-growth-sandbox"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v curl >/dev/null || fail "curl is required"
command -v jq >/dev/null || fail "jq is required"
curl -fsS "${API_BASE_URL}/health" >/dev/null || fail "SDQ API is unavailable at ${API_BASE_URL}"

tenants="$(curl -fsS "${API_BASE_URL}/tenants")"
jq -e --arg slug "${TENANT_SLUG}" '.tenants[] | select(.slug == $slug)' <<<"${tenants}" >/dev/null \
  || fail "Sandbox tenant does not exist"

imports="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/imports?channel=google_ads")"
jq -e '.imports | length >= 3' <<<"${imports}" >/dev/null || fail "Expected at least three Google Ads imports"

tasks="$(curl -fsS "${API_BASE_URL}/tasks/${TENANT_SLUG}")"
jq -e '.tasks[] | select(.title == "Baseline Google Ads performance analysis")' <<<"${tasks}" >/dev/null \
  || fail "Baseline task missing"
jq -e '.tasks[] | select(.title == "Follow-up Google Ads performance analysis")' <<<"${tasks}" >/dev/null \
  || fail "Followup task missing"
jq -e '.tasks[] | select(.title == "Validation Google Ads performance analysis")' <<<"${tasks}" >/dev/null \
  || fail "Validation task missing"

runs="$(curl -fsS "${API_BASE_URL}/agent-runs/${TENANT_SLUG}")"
jq -e '.agent_runs[] | select(.status == "completed")' <<<"${runs}" >/dev/null \
  || fail "No completed agent run found"

approvals="$(curl -fsS "${API_BASE_URL}/approvals/${TENANT_SLUG}")"
jq -e '.approvals[] | select(.status == "approved" and .reviewed_by == "Sharif")' <<<"${approvals}" >/dev/null \
  || fail "No approved demo approval reviewed by Sharif found"

memory="$(curl -fsS "${API_BASE_URL}/memory/${TENANT_SLUG}")"
jq -e '.memory_items | length >= 1' <<<"${memory}" >/dev/null || fail "No memory item found"

candidates="$(curl -fsS "${API_BASE_URL}/improvement-candidates/${TENANT_SLUG}")"
jq -e '.improvement_candidates[] | select(.status == "approved")' <<<"${candidates}" >/dev/null \
  || fail "No approved improvement candidate found"

proposals="$(curl -fsS "${API_BASE_URL}/evolution/proposals?status=approved")"
latest_proposed_version="$(jq -r '.evolution_proposals[0].proposed_version // empty' <<<"${proposals}")"
[[ -n "${latest_proposed_version}" ]] || fail "No approved evolution proposal found"

skills="$(curl -fsS "${API_BASE_URL}/skills")"
jq -e --arg version "${latest_proposed_version}" \
  '.skills[] | select(.slug == "google-ads-performance-analysis") | .latest_approved_version.version == $version' \
  <<<"${skills}" >/dev/null || fail "Newest skill version is not active"

baseline="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-06-01&date_to=2026-06-07")"
followup="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-06-15&date_to=2026-06-21")"
validation="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-07-01&date_to=2026-07-07")"

jq -e '.summary.alerts[] | select(.campaign_name == "Broad Growth Experiments")' <<<"${baseline}" >/dev/null \
  || fail "Expected Broad Growth Experiments baseline alert missing"

baseline_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${baseline}")"
followup_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${followup}")"
validation_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${validation}")"
baseline_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${baseline}")"
followup_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${followup}")"
validation_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${validation}")"
awk -v b="${baseline_cpa}" -v f="${followup_cpa}" -v v="${validation_cpa}" 'BEGIN { exit !(f < b && v < b) }' \
  || fail "CPA improvement did not persist"
awk -v b="${baseline_roas}" -v f="${followup_roas}" -v v="${validation_roas}" 'BEGIN { exit !(f > b && v > b) }' \
  || fail "ROAS improvement did not persist"

other_tasks="$(curl -fsS "${API_BASE_URL}/tasks/demo-partner-a" || true)"
if jq -e '.tasks[]?.title | select(test("Baseline Google Ads performance analysis|Follow-up Google Ads performance analysis|Validation Google Ads performance analysis"))' <<<"${other_tasks}" >/dev/null 2>&1; then
  fail "Sandbox task leaked into demo-partner-a"
fi

paperclip_status="unavailable"
if curl -fsS "${PAPERCLIP_URL}/health" >/dev/null 2>&1; then
  paperclip_status="available"
fi

hermes_status="unavailable"
gateway_env="${REPO_ROOT}/runtime/hermes/gateway/.env"
if [[ -f "${gateway_env}" ]]; then
  api_key="$(grep '^API_SERVER_KEY=' "${gateway_env}" | sed 's/^API_SERVER_KEY=//')"
  if [[ -n "${api_key}" ]] && curl -fsS -H "Authorization: Bearer ${api_key}" "${HERMES_GATEWAY_URL}/health" >/dev/null 2>&1; then
    hermes_status="available"
  fi
fi

if [[ "${paperclip_status}" != "available" ]]; then
  fail "Paperclip integration health is not available"
fi
if [[ "${hermes_status}" != "available" ]]; then
  fail "Hermes Gateway integration health is not available"
fi

echo "demo verification passed"

