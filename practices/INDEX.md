# Practices Index

Patterns and conventions extracted from production repos. Reference these when starting new projects or making architectural decisions.

## Architecture

- [FastAPI Structure](architecture/fastapi-structure.md) — Route organization, service layers, migrations
- [Database Patterns](architecture/database-patterns.md) — PostgreSQL, SQLite, FTS, RLS, upserts
- [Data-Quality Checks](architecture/data-quality-checks.md) — Result contract, calibrating both directions, derived registration, write-path gate, check isolation, alert paths
- [Pydantic & Data Models](architecture/pydantic-patterns.md) — Settings, API models, TypeScript types
- [Resilience](architecture/resilience.md) — Circuit breaker, run governor, retry, async error gathering
- [Logging](architecture/logging.md) — Structlog conventions, event naming
- [Config Management](architecture/config-management.md) — Env vars, YAML, CSV, DB config with TTL
- [Testing](architecture/testing.md) — FastAPI TestClient, mock DB, auth fixtures
- [Mobile Patterns](architecture/mobile-patterns.md) — Expo Router, platform-specific files, data sync

## AI

- [Gemini Integration](ai/gemini-integration.md) — Client setup, model selection, batch processing, Edge Functions
- [Prompt Engineering](ai/prompt-engineering.md) — Classification, context-aware, structured output, code review
- [LLM Evaluation & Prompt-Regression](ai/llm-evaluation.md) — Golden/fixture datasets, task-appropriate metrics, CI regression gate, model-upgrade gating, drift monitoring

## AI Safety

- [Prompt Injection Mitigation](ai-safety/prompt-injection-mitigation.md) — XML tag wrapping, negative instructions, input isolation
- [Agent Action Safety & Control Layers](ai-safety/agent-action-safety.md) — Action tiers, least-privilege/read-only, judge layer, human-in-the-loop, authorization specs, audit trail

## Security

- [Secrets Management](security/secrets-management.md) — Env vars, GCP Secret Manager, Fernet, auth, rate limiting
- [SQL Injection Prevention](security/sql-injection-prevention.md) — Parameterized queries, %s placeholders, ILIKE escaping

## DevOps

- [Cloud Run](devops/cloud-run.md) — Two-image pattern, env vars, multi-stage Docker, autoscaling
- [CI/CD](devops/ci-cd.md) — GitHub Actions, Cloud Build, automated reviews
- [Windows / WSL Boundary](devops/windows-wsl-boundary.md) — `.gitattributes` line-ending pins, why `git status` can't see CRLF corruption, cross-boundary verification gotchas

## Finance & Investing

- [AI for Finance](finance/ai-for-finance.md) — Accounting automation, classification, forecasting, data aggregation
- [Investing Patterns](finance/investing-patterns.md) — Portfolio architecture, macro analysis, spending categories, Plaid, client-ready patterns
- [Payroll & Labor](finance/payroll-patterns.md) — Payroll engine, OT rules, time integration, labor analytics

## Writing

- [Personal Voice Memory](writing/voice-memory.md) — Capture + reconciliation mechanism: `feedback_voice_*` captures at `/wrap-up`, monthly `/voice-sync` into the private master (command-center `knowledge/voice/master.md`), public-repo boundary
- [Email Drafting](writing/email-drafting.md) — The process half: brevity mechanics, range-as-floor, non-binding caps, no-summary-in-prompt, live A/B as the acceptance test

## Development

- [Payroll Testing](development/payroll-testing.md) — Decimal precision, OT edge cases, tip distribution, known-good validation

## Reviews

Shared review prompts live in [`/reviews/`](../reviews/). Update once, applies to all repos.
See [`/reviews/README.md`](../reviews/README.md) for setup instructions.

## Claude Code

- [CLAUDE.md Structure](claude-code/claude-md-structure.md) — Root + module templates, knowledge system, decision journal, layered architecture, rules/hooks/skills/agents
- [Context & Memory Management](claude-code/context-memory-management.md) — Memory tiers, retrieval contracts / sources of truth, context budget & session moves, anti-fragmentation, skills as institutional memory, provenance
- [CLI Patterns](claude-code/cli-patterns.md) — Click structure, common flags, command groups
- [Code Review & Preventing AI Slop](claude-code/code-review-and-ai-slop.md) — Spec-first, defend-the-reasoning, real-environment validation, AI-code-review checklist, destructive-action gating, cleanup-tax telemetry
- [Model-Hierarchy Delegation](claude-code/model-hierarchy-delegation.md) — Brain-vs-hands, tier rules (Fable/Opus/Sonnet/Haiku), when to delegate, depth cap 2, structured returns, judgment stays with the parent
- [Token Efficiency](claude-code/token-efficiency.md) — Cache misses, context bloat, model routing, input format
- [Remote Access](claude-code/remote-access.md) — Web Sessions, Remote Control, Dispatch, Channels
- [Surface Guide](claude-code/surface-guide.md) — Chat vs. Cowork vs. Code Tab vs. Code CLI
