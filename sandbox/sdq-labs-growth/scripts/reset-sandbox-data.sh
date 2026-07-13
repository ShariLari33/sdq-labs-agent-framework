#!/usr/bin/env bash
set -euo pipefail

TENANT_SLUG="sdq-labs-growth-sandbox"
DB_CONTAINER="${DB_CONTAINER:-sdq-postgres}"
DB_NAME="${DB_NAME:-sdq_agents}"
DB_USER="${DB_USER:-sdq}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v docker >/dev/null || fail "docker is required"
docker ps --format '{{.Names}}' | grep -qx "${DB_CONTAINER}" || fail "Database container ${DB_CONTAINER} is not running"

docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 -v tenant_slug="${TENANT_SLUG}" >/dev/null <<'SQL'
WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug'),
target_candidates AS (SELECT ic.id FROM improvement_candidates ic JOIN target t ON t.id = ic.tenant_id)
DELETE FROM skill_versions
WHERE source_improvement_candidate_id IN (SELECT id FROM target_candidates);

UPDATE skill_versions
SET status = 'approved'
WHERE skill_id = (SELECT id FROM skills WHERE slug = 'google-ads-performance-analysis')
  AND version = '0.1.0';

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug'),
target_candidates AS (SELECT ic.id FROM improvement_candidates ic JOIN target t ON t.id = ic.tenant_id)
DELETE FROM evolution_proposals WHERE improvement_candidate_id IN (SELECT id FROM target_candidates);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug'),
target_candidates AS (SELECT ic.id FROM improvement_candidates ic JOIN target t ON t.id = ic.tenant_id)
DELETE FROM candidate_evaluations WHERE improvement_candidate_id IN (SELECT id FROM target_candidates);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug'),
target_candidates AS (SELECT ic.id FROM improvement_candidates ic JOIN target t ON t.id = ic.tenant_id)
DELETE FROM candidate_evidence WHERE improvement_candidate_id IN (SELECT id FROM target_candidates);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM performance_feedback WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM events WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM approvals WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM learnings WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM memory_items WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM improvement_candidates WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM agent_runs WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM tasks WHERE tenant_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM tenants WHERE slug = :'tenant_slug')
DELETE FROM performance_imports WHERE tenant_id IN (SELECT id FROM target);
SQL

echo "reset completed for ${TENANT_SLUG}"
