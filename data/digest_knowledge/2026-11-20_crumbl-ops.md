# Digest: crumbl-ops — 2026-11-20

## Top Posts

- **200 OK is dead as an AI agent health signal. Here’s what comes next.** (The New Stack) — relevance 7/10
  Standard APM metrics fail to detect AI agent errors because fallback handlers return 200 OK even when classification accuracy drops or valid inputs are rejected. The article advocates treating silent agent defects with active verification barriers and offline sampling of production traces rather than relying on HTTP status codes.
  Why: crumbl-ops runs production LLM classifications in src/cs/ and src/ops/ where silent fallback failures would register as successful HTTP 200 responses in Cloud Run.

- **Anthropic says Claude writes and reviews 90% of its team’s code. The catch is how it checks the work.** (The New Stack) — relevance 6/10
  Anthropic details how the Claude Code development team manages agent-generated PRs through repository-scoped verification skills in .claude/skills/, property-based testing, and live application execution before committing code.
  Why: crumbl-ops uses Claude Code as its primary engineering partner with custom .claude/skills/ and verification chokepoints.

- **“We are not querying like humans anymore”: OpenSearch’s Bianca Lewis on why AI agent mistakes look like successes** (The New Stack) — relevance 6/10
  Traditional observability assumes failures return 500 status codes, but agents frequently call the wrong API or retrieve inaccurate data while every individual step returns 200 OK. Monitoring must evolve from error tracking to inspecting the causal sequence of tool calls and downstream state transitions.
  Why: Directly addresses observability gaps in multi-step AI operations like crumbl-ops' dual-model reviews and morning digest synthesis.

- **[AINews] Gemini 4 Neon: GDM's Opus/Sol Contender** (Latent Space) — relevance 5/10
  Google DeepMind released Gemini 4 Neon, retiring Argon and positioning Neon as a faster, lower-cost reasoning model with a 1M-token context window. Neon is priced at $3/M input and $15/M output tokens.
  Why: crumbl-ops uses Gemini in src/cs/ and src/ops/ with strict model string pinning enforced by tests/test_model_strings_pinned.py.

- **Postgres 19 is here (GTA VI can wait)** (Postgres Weekly) — relevance 5/10
  Postgres 19 released with concurrent table repacking without blocking reads/writes, INSERT ... ON CONFLICT DO SELECT for single round-trip get-or-create operations, and plan stability extensions pg_plan_advice and pg_stash_advice.
  Why: crumbl-ops relies on PostgreSQL for core state and transaction persistence, though it currently runs on PostgreSQL 17.
