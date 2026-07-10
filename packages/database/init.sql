CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  version TEXT NOT NULL DEFAULT '0.1.0',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  input JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  task_id UUID REFERENCES tasks(id),
  agent_template_id UUID REFERENCES agent_templates(id),
  status TEXT NOT NULL DEFAULT 'queued',
  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  logs JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learnings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  scope TEXT NOT NULL DEFAULT 'partner',
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  confidence TEXT NOT NULL DEFAULT 'medium',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO tenants (name, slug)
VALUES
  ('SDQ Labs Internal', 'sdq-labs-internal'),
  ('Demo Partner A', 'demo-partner-a'),
  ('Demo Partner B', 'demo-partner-b')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  task_id UUID NOT NULL REFERENCES tasks(id),
  status TEXT NOT NULL DEFAULT 'pending',
  requested_by TEXT,
  reviewed_by TEXT,
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS worker_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  worker_type TEXT NOT NULL,
  endpoint TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO agent_templates (name, description, version)
VALUES
  ('Google Ads Performance Analyst', 'Analyses Google Ads performance data and creates optimisation recommendations.', '0.1.0')
ON CONFLICT DO NOTHING;

INSERT INTO worker_registry (name, worker_type, endpoint)
VALUES
  ('mock-performance-worker', 'mock', NULL)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skill_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id UUID NOT NULL REFERENCES skills(id),
  version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(skill_id, version)
);

CREATE TABLE IF NOT EXISTS agent_template_skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_template_id UUID NOT NULL REFERENCES agent_templates(id),
  skill_id UUID NOT NULL REFERENCES skills(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(agent_template_id, skill_id)
);

INSERT INTO skills (name, slug, description, status)
VALUES (
  'Google Ads Performance Analysis',
  'google-ads-performance-analysis',
  'Analyses Google Ads performance and creates optimisation recommendations.',
  'approved'
)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO skill_versions (skill_id, version, status, content)
SELECT
  s.id,
  '0.1.0',
  'approved',
  '# Google Ads Performance Analysis Skill

## Purpose
Analyse Google Ads performance data and identify optimisation opportunities.

## Process
1. Review spend, conversions, CPA, ROAS and conversion rate.
2. Identify wasted spend.
3. Identify campaigns or segments with strong performance.
4. Recommend concrete next actions.
5. Create a learning candidate when a reusable pattern is found.

## Output
Return summary, findings, recommendations and learning candidates.

## Approval
Human approval is required before any external change.'
FROM skills s
WHERE s.slug = 'google-ads-performance-analysis'
ON CONFLICT (skill_id, version) DO NOTHING;

INSERT INTO agent_template_skills (agent_template_id, skill_id)
SELECT at.id, s.id
FROM agent_templates at
JOIN skills s ON s.slug = 'google-ads-performance-analysis'
WHERE at.name = 'Google Ads Performance Analyst'
ON CONFLICT (agent_template_id, skill_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS memory_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  memory_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  status TEXT NOT NULL DEFAULT 'active',
  confidence TEXT NOT NULL DEFAULT 'medium',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS improvement_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id),
  candidate_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source_task_id UUID REFERENCES tasks(id),
  source_agent_run_id UUID REFERENCES agent_runs(id),
  status TEXT NOT NULL DEFAULT 'proposed',
  reviewed_by TEXT,
  review_comment TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS capabilities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  default_model_tier TEXT DEFAULT 'standard',
  approval_required BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capability_workers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capability_id UUID REFERENCES capabilities(id),
  worker_id UUID REFERENCES worker_registry(id),
  channel TEXT,
  priority INT DEFAULT 100,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(capability_id, worker_id, channel)
);

CREATE TABLE IF NOT EXISTS capability_skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capability_id UUID REFERENCES capabilities(id),
  skill_id UUID REFERENCES skills(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(capability_id, skill_id)
);

CREATE TABLE IF NOT EXISTS model_routes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type TEXT NOT NULL,
  sensitivity TEXT NOT NULL DEFAULT 'internal',
  cost_tier TEXT NOT NULL DEFAULT 'low',
  quality_tier TEXT NOT NULL DEFAULT 'standard',
  provider TEXT NOT NULL,
  model_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO capabilities (
  slug,
  name,
  description,
  default_model_tier,
  approval_required
)
VALUES (
  'performance_analysis',
  'Performance Analysis',
  'Analyse marketing performance data and generate recommendations.',
  'standard',
  true
)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO capability_workers (capability_id, worker_id, channel)
SELECT c.id, w.id, 'google_ads'
FROM capabilities c
JOIN worker_registry w ON w.name = 'mock-performance-worker'
WHERE c.slug = 'performance_analysis'
ON CONFLICT (capability_id, worker_id, channel) DO NOTHING;

INSERT INTO capability_skills (capability_id, skill_id)
SELECT c.id, s.id
FROM capabilities c
JOIN skills s ON s.slug = 'google-ads-performance-analysis'
WHERE c.slug = 'performance_analysis'
ON CONFLICT (capability_id, skill_id) DO NOTHING;

INSERT INTO model_routes (
  task_type,
  sensitivity,
  cost_tier,
  quality_tier,
  provider,
  model_name
)
SELECT
  'performance_analysis',
  'internal',
  'low',
  'standard',
  'mock',
  'mock-model-v0'
WHERE NOT EXISTS (
  SELECT 1
  FROM model_routes
  WHERE task_type = 'performance_analysis'
    AND sensitivity = 'internal'
    AND cost_tier = 'low'
    AND quality_tier = 'standard'
    AND provider = 'mock'
    AND model_name = 'mock-model-v0'
);
