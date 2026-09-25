# Digest: crumbl-ops — 2026-09-25

## Top Posts

- **Anthropic made Opus 5.5 cheaper. Then it broke four things your agent depends on.** (The New Stack) — relevance 10/10
  Claude Opus 5.5 introduces breaking changes for agents, including making "thinking" always on (controlled by `effort`), deprecating "forced tool calls" (now using `auto` combined with system prompts), and altering system prompt parsing. These changes can cause existing Claude 5 agent requests to return 400 errors or behave unexpectedly if not adapted during migration.
  Why: This post is critically relevant as crumbl-ops extensively uses Claude Code and headless `claude -p` jobs, requiring immediate attention to these breaking changes for a smooth upgrade to Opus 5.5.

- **Tutorial: Replace Your $3K/month Data Analyst With a Claude Skill** (The AI Break) — relevance 9/10
  This tutorial shows how to build Claude Skills for automated data analysis, featuring a "METRICS CORE" for defining key business numbers, an "EXPORT MAP" for spreadsheet structures, and "Report Desk" and "Delta Watch" skills to generate financial reports and variance analyses from uploaded data.
  Why: This directly addresses the CFO's interest in automated financial reporting and variance analysis by providing a concrete, skill-based approach to augment existing reporting workflows using Claude.

- **Advanced evals: How to find (and fix) hidden AI failures in your product** (Lenny's Newsletter) — relevance 9/10
  The article discusses advanced techniques for LLM evaluation, focusing on identifying and correcting subtle AI failures in products by measuring the right things. It highlights automation in evaluation and mentions a plugin to help coding agents with the heavy lifting in this process.
  Why: Although crumbl-ops has an LLM eval harness, this post offers specific, advanced techniques to refine AI-driven testing/QA and forecast model evaluation, particularly in finding subtle failures and improving reliability.

- **Scribd, Inc. classifies more than 400 million documents with Gemini batch inference on Gemini Enterprise** (Google Cloud Blog) — relevance 9/10
  Scribd successfully uses Gemini's batch inference capabilities on Gemini Enterprise to classify over 400 million documents, demonstrating its robust performance for large-scale content categorization.
  Why: This is highly relevant to the CFO's interest in LLMs for document extraction (like receipts and tax forms) and expands on crumbl-ops' current Gemini usage for email classification, suggesting scalable patterns for new document types.

- **How Warp ships 2,000 PRs a month with AI factories | Zach Lloyd (CEO, Warp)** (Lenny's Newsletter) — relevance 9/10
  Zach Lloyd discusses Warp's AI software factory, Wilson, which automates a Slack to GitHub QA workflow to ship 2,000 PRs monthly. The process emphasizes managing human review as a bottleneck, scoring agent runs, identifying failure modes, and using task replays for cost/quality tradeoffs.
  Why: Given crumbl-ops already uses an AI software factory, this post offers concrete, actionable insights into optimizing throughput, identifying bottlenecks in human review, and improving agent reliability, directly supporting scaling small-team engineering and technical debt management.

## Recommendations

- [MEDIUM] Upgrade Claude to Opus 5.5 and adapt agent call patterns
  Upgrade Claude models to Opus 5.5 and systematically review and update all existing Claude Code and headless `claude -p` call sites. Specifically, refactor any logic relying on the deprecated `thinking` parameter to use the `effort` parameter, replace explicit `tool_choice` calls with the `auto` setting combined with enhanced `system_prompt` guidance, and ensure code anticipates the new behavior of `thinking` blocks always appearing first in responses.
  Inspired by: Anthropic made Opus 5.5 cheaper. Then it broke four things your agent depends on. (Post 178)
  Impact: Ensures continued compatibility with the latest Claude model, potentially reducing costs and improving response quality/speed for existing agentic workflows and narratives, while mitigating the risk of operational failures due to breaking API changes.
  Where it fits: CLAUDE.md (model pinning), .claude/skills/ (tool calls), src/cs/ (Gemini/Claude integration), src/ops/ (Gemini/Claude reporting, scheduled jobs), tests/test_model_strings_pinned.py (validation).
  First step: Create a dedicated branch for Opus 5.5 migration, identify all Claude call sites, and perform a dry run of critical scheduled jobs (e.g., month-end CFO narrative, weekly BI report) against Opus 5.5 with default settings to observe new thinking block behavior and tool call patterns.
  Risks: Requires significant refactoring effort across all Claude integrations; potential for subtle behavioral shifts not immediately apparent from API errors; careful testing needed to ensure no degradation in narrative quality or tool execution for critical financial and operational workflows.

- [MEDIUM] Develop Claude Skills for on-demand financial reporting from exports
  Build a set of dedicated Claude skills, analogous to "The Numbers Desk" from the article. This involves creating a `METRICS CORE` definition for key financial performance indicators (e.g., sales growth, labor cost as % of sales) within `knowledge/`, and an `EXPORT MAP` configuration for common spreadsheet data sources (e.g., DoorDash, UberEats, or ad-hoc QBO exports). Implement 'Report Desk' and 'Delta Watch' skills to leverage these definitions, allowing the owner to drop in data and automatically generate a one-page summary or variance analysis, streamlining current `src/ops/` reporting and `month_end_review` processes.
  Inspired by: Tutorial: Replace Your $3K/month Data Analyst With a Claude Skill (Post 15)
  Impact: Significantly automates repetitive financial data analysis from various sources, providing the CFO with faster, standardized insights and variance tracking. This reduces manual effort in consolidating and analyzing ad-hoc reports beyond existing automated processes, directly addressing the interest in automated financial reporting.
  Where it fits: .claude/skills/ (new financial analysis skills), knowledge/ (structured metrics and export maps), src/ops/ (integration with existing reporting, or new entry points for ad-hoc analysis).
  First step: Identify one recurring manual spreadsheet analysis workflow (e.g., weekly marketplace reconciliation or labor cost analysis) currently performed by the owner. Define its key metrics and an `EXPORT MAP` structure for its input data, then build a minimal Claude skill to generate a basic 'Report Desk' summary from a sample input file.
  Risks: Ensuring the LLM accurately interprets and calculates financial metrics from varied spreadsheet formats can be challenging; requires careful validation against ground truth; the quality of output is highly dependent on the `METRICS CORE` and `EXPORT MAP` definitions; potential for 'hallucinations' if data is ambiguous or definitions are underspecified.
