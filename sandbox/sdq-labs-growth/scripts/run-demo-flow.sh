#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PAPERCLIP_URL="${PAPERCLIP_URL:-http://localhost:3100}"
HERMES_GATEWAY_URL="${HERMES_GATEWAY_URL:-http://localhost:8642}"
TENANT_SLUG="sdq-labs-growth-sandbox"
TENANT_NAME="SDQ Labs Growth Sandbox"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

json_post() {
  local url="$1"
  local payload="$2"
  curl -fsS -X POST "${url}" -H "Content-Type: application/json" -d "${payload}"
}

wait_for_api() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS "${API_BASE_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

run_period() {
  local label="$1"
  local task_file="$2"
  local expected_campaign="$3"

  local task_response run_response approval_id task_id run_id
  task_response="$(curl -fsS -X POST "${API_BASE_URL}/tasks" \
    -H "Content-Type: application/json" \
    --data-binary "@${task_file}")"
  task_id="$(jq -r '.task.id' <<<"${task_response}")"
  [[ -n "${task_id}" && "${task_id}" != "null" ]] || fail "Could not create ${label} task"

  run_response="$(curl -fsS -X POST "${API_BASE_URL}/task-engine/run-next/${TENANT_SLUG}")"
  jq -e '.task.status == "needs_review"' <<<"${run_response}" >/dev/null \
    || fail "${label} task was not moved to needs_review"
  jq -e '.agent_run.status == "completed"' <<<"${run_response}" >/dev/null \
    || fail "${label} agent run did not complete"
  jq -e '.output.approval_required == true' <<<"${run_response}" >/dev/null \
    || fail "${label} output did not require approval"
  jq -e --arg campaign "${expected_campaign}" '.output.findings[]?.campaign | select(. == $campaign)' <<<"${run_response}" >/dev/null \
    || fail "${label} output was not grounded in ${expected_campaign}"

  approval_id="$(jq -r '.approval.id' <<<"${run_response}")"
  run_id="$(jq -r '.agent_run.id' <<<"${run_response}")"
  json_post "${API_BASE_URL}/approvals/${approval_id}/approve" \
    '{"reviewed_by":"Sharif","comment":"Approved for synthetic sandbox demo."}' >/dev/null \
    || fail "Could not approve ${label} approval"

  printf '%s\n' "${run_id}"
}

command -v curl >/dev/null || fail "curl is required"
command -v jq >/dev/null || fail "jq is required"
wait_for_api || fail "SDQ API is unavailable at ${API_BASE_URL}"

"${ROOT_DIR}/scripts/bootstrap.sh" >/dev/null
"${ROOT_DIR}/scripts/reset.sh"
"${ROOT_DIR}/scripts/import-baseline.sh"
"${ROOT_DIR}/scripts/import-followup.sh"
"${ROOT_DIR}/scripts/import-validation.sh"

baseline_run_id="$(run_period "baseline" "${ROOT_DIR}/tasks/baseline-analysis.json" "Broad Growth Experiments")"
followup_run_id="$(run_period "followup" "${ROOT_DIR}/tasks/followup-analysis.json" "Brand Search")"
validation_run_id="$(run_period "validation" "${ROOT_DIR}/tasks/validation-analysis.json" "Brand Search")"

baseline_summary="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-06-01&date_to=2026-06-07")"
followup_summary="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-06-15&date_to=2026-06-21")"
validation_summary="$(curl -fsS "${API_BASE_URL}/performance-data/${TENANT_SLUG}/google-ads/summary?date_from=2026-07-01&date_to=2026-07-07")"

baseline_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${baseline_summary}")"
followup_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${followup_summary}")"
validation_cpa="$(jq -r '.summary.calculated_metrics.cost_per_conversion' <<<"${validation_summary}")"
baseline_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${baseline_summary}")"
followup_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${followup_summary}")"
validation_roas="$(jq -r '.summary.calculated_metrics.roas' <<<"${validation_summary}")"

awk -v b="${baseline_cpa}" -v f="${followup_cpa}" 'BEGIN { exit !(f < b) }' \
  || fail "Expected lower followup CPA"
awk -v b="${baseline_roas}" -v f="${followup_roas}" 'BEGIN { exit !(f > b) }' \
  || fail "Expected improved followup ROAS"
awk -v b="${baseline_cpa}" -v v="${validation_cpa}" 'BEGIN { exit !(v < b) }' \
  || fail "Expected validation CPA to remain better than baseline"
awk -v b="${baseline_roas}" -v v="${validation_roas}" 'BEGIN { exit !(v > b) }' \
  || fail "Expected validation ROAS to remain better than baseline"

json_post "${API_BASE_URL}/performance-feedback/${TENANT_SLUG}" "{
  \"agent_run_id\": \"${followup_run_id}\",
  \"metric_name\": \"cost_per_conversion\",
  \"metric_value\": ${followup_cpa},
  \"metric_unit\": \"EUR\",
  \"baseline_value\": ${baseline_cpa},
  \"period_start\": \"2026-06-15T00:00:00Z\",
  \"period_end\": \"2026-06-21T23:59:59Z\",
  \"metadata\": {\"source\": \"sandbox-demo\", \"comparison\": \"followup_vs_baseline\"}
}" >/dev/null || fail "Could not create performance feedback"

candidate_id="$(curl -fsS "${API_BASE_URL}/improvement-candidates/${TENANT_SLUG}" \
  | jq -r '.improvement_candidates[0].id // empty')"
[[ -n "${candidate_id}" ]] || fail "No learning/improvement candidate was created"

json_post "${API_BASE_URL}/improvement-candidates/${candidate_id}/approve" \
  '{"reviewed_by":"Sharif","review_comment":"Approved for synthetic sandbox evolution."}' >/dev/null \
  || fail "Could not approve improvement candidate"
curl -fsS -X POST "${API_BASE_URL}/evolution/analyse/${candidate_id}" >/dev/null \
  || fail "Could not analyse improvement candidate"

proposal_response="$(curl -sS -X POST "${API_BASE_URL}/evolution/proposals/from-candidate/${candidate_id}")"
proposal_status="$?"
if [[ "${proposal_status}" != "0" ]]; then
  fail "Could not create evolution proposal"
fi
proposal_id="$(jq -r '.evolution_proposal.id // empty' <<<"${proposal_response}")"
[[ -n "${proposal_id}" ]] || fail "Evolution proposal response did not include an id"

approval_response="$(json_post "${API_BASE_URL}/evolution/proposals/${proposal_id}/approve" \
  '{"reviewed_by":"Sharif","comment":"Approved after synthetic sandbox evidence review."}')"
latest_skill_version="$(jq -r '.skill_version.version // empty' <<<"${approval_response}")"
[[ -n "${latest_skill_version}" ]] || fail "Evolution approval did not return a skill version"

skills_response="$(curl -fsS "${API_BASE_URL}/skills")"
jq -e --arg version "${latest_skill_version}" \
  '.skills[] | select(.slug == "google-ads-performance-analysis") | .latest_approved_version.version == $version' \
  <<<"${skills_response}" >/dev/null || fail "Newest skill version is not active"

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

"${ROOT_DIR}/scripts/verify-demo.sh" >/dev/null

latest_run="$(curl -fsS "${API_BASE_URL}/agent-runs/${TENANT_SLUG}" | jq -r '.agent_runs[0].id')"
tasks_count="$(curl -fsS "${API_BASE_URL}/tasks/${TENANT_SLUG}" | jq -r '.tasks | length')"

cat <<EOF
=========================
SANDBOX READY
=========================
tenant: ${TENANT_NAME} (${TENANT_SLUG})
campaigns: Brand Search, AI Automation Non Brand, Broad Growth Experiments
tasks: ${tasks_count}
latest run: ${latest_run}
latest skill version: ${latest_skill_version}
Paperclip status: ${paperclip_status}
Hermes status: ${hermes_status}
baseline CPA=${baseline_cpa} ROAS=${baseline_roas}
followup CPA=${followup_cpa} ROAS=${followup_roas}
validation CPA=${validation_cpa} ROAS=${validation_roas}
EOF
