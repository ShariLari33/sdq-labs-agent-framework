# ADR-0004 — Evolution Engine

## Status
Accepted

## Context
The framework must improve over time based on agent output, human feedback and measurable performance.

A language model does not truly retrain itself during normal task execution. Improvement is achieved by updating:

- partner memory
- global memory
- skills
- tools
- model routes
- worker configuration

These updates must remain reviewable, versioned and reversible.

## Decision
Introduce an Evolution Engine that converts run outcomes and performance feedback into governed improvement proposals.

## Architecture

Agent Run
↓
Output and feedback
↓
Evidence collection
↓
Learning classification
↓
Improvement candidate
↓
Evaluation
↓
Human review
↓
Approved versioned change
↓
Future executions use updated configuration

## Learning Classes

### Partner Learning
Applies only to one tenant.

### Global Learning
Anonymised and reusable across tenants.

### Skill Improvement
Proposed change to a reusable skill.

### Tool Improvement
Proposed change to a query, connector or workflow.

### Model Route Improvement
Proposed change to model selection rules.

### Worker Improvement
Proposed change to worker implementation or configuration.

## Evidence Requirements
No production improvement may be approved solely because an LLM suggested it.

Candidates should reference evidence such as:

- source agent runs
- approval feedback
- rejection feedback
- performance metrics
- repeated patterns
- evaluation results

## Governance
The engine may automatically:

- collect evidence
- classify learnings
- group similar candidates
- draft proposed changes
- run evaluations
- recommend approval or rejection

The engine may not automatically:

- approve production skill versions
- change production tools
- change external write permissions
- promote partner data to global memory
- deploy code

## Skill Promotion
When a skill improvement is approved:

1. Create a new draft skill version.
2. Store the previous approved version.
3. Run evaluation cases.
4. Require human approval.
5. Mark the new version approved.
6. Future runs resolve the new approved version automatically.
7. Existing historical runs remain pinned to their original version.

## Rollback
Every approved change must be reversible by restoring the previous approved version.

## Initial Scope
Evolution Engine v0.1 supports:

- performance feedback records
- evidence links
- candidate evaluation
- draft skill-version generation
- manual promotion
- rollback metadata
