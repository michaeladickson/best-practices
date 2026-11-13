# Digest: crumbl-ops — 2026-11-13

## Top Posts

- **UUIDv4 vs UUIDv7: What a Random Primary Key Costs** (Postgres Weekly) — relevance 7/10
  PostgresAI benchmarks demonstrate that random UUIDv4 primary keys degrade insert throughput by a third and significantly inflate WAL generation once indexes exceed cache limits. Sequential UUIDv7 addresses this by maintaining B-tree locality while preserving random UUID properties.
  Why: crumbl-ops operates on PostgreSQL 17 across six store entities plus an isolated external tenant, where transaction volume and index cache efficiency directly affect Cloud Run database performance.

- **Claude Code's "Don't Ask Again" exposes passwords in 1,122 public GitHub files** (Hacker News: claude code (50+ points)) — relevance 6/10
  Apiiro reports widespread leaks of credentials and secrets into public repositories caused by developers auto-approving coding agent actions via permissive modes. Suppressing confirmation prompts allows agents to inadvertently stage and commit sensitive local configuration files.
  Why: Validates the existing design of crumbl-ops's deterministic PreToolUse Bash hooks and git push gates that prevent autonomous leakage of sensitive operational credentials.

- **Quoting Prompting Claude Fable 5.2** (Simon Willison) — relevance 5/10
  Anthropic testing indicates that explicitly prompting Claude with codebase ownership ('You are the owner and long-term maintainer of this codebase...') boosts automatic consolidation of duplicated code from under 10% to 75% of runs.
  Why: The prompt framing technique is relevant for steering headless Claude Code maintenance jobs like weekly memory consolidation and monthly knowledge curation.

- **Gemini Decisions API** (Simon Willison) — relevance 5/10
  Google released Gemini Decision 1, offering fast (~200ms) calibrated probability distributions over predefined choices and rubrics at low cost ($0.10/M tokens) without generating conversational text.
  Why: Because Gemini is already an approved and integrated provider in src/cs/ and src/ops/, changes to Google's classification capabilities are worth monitoring even though existing heuristics meet current needs.
