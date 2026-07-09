# ADR-0001 — Core Framework Architecture

## Status
Accepted

## Context
SDQ Labs Agent Framework must support multiple tenants, reusable agents, future Hermes integration, existing Claude Code/VPS agents, Paperclip UI integration, Slack commands, performance analysis, approvals, and learning loops.

The framework should not be built around one agent runtime. Hermes, Claude Code workers, Python workers, n8n workflows and future runtimes must all be able to execute work through the same core protocol.

## Decision
The platform will be task-first and event-driven.

A task is the central unit of work. Agents, workers, tools, skills, memory and models are selected around the task.

Core components:

1. Task Engine
2. Event Bus
3. Agent Registry
4. Skill Registry
5. Memory Registry
6. Learning Pipeline
7. Model Router
8. Worker Protocol
9. Approval System
10. Audit Log

## Architecture

```text
Task Created
↓
Event emitted
↓
Task Engine selects agent template
↓
Skill Registry resolves approved skills
↓
Memory Registry resolves tenant-specific and global context
↓
Model Router selects model
↓
Worker Protocol executes task
↓
Output generated
↓
Approval requested
↓
Learning Pipeline creates candidates
↓
Future runs use updated memory and approved skill versions
