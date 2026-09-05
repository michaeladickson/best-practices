# Digest: crumbl-ops — 2026-09-05

## Top Posts

- **This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling** (Claude Code weekly newsletter (email)) — relevance 10/10
  Anthropic's Claude Code updates include enhanced session mobility, new tools for session identification, immediate project setting application with /cd, improved memory for subagents, partial results, editable auto-mode permissions, a restricted mode, and workflow patterns like /recap and adversarial pre-review.
  Why: This post directly addresses multiple key areas for crumbl-ops, especially 'Making Claude Code sessions more efficient (hooks, skills, memory, session management)' and 'AI agents for operations', with specific, actionable feature descriptions.

- **AI Agents built a 3D city for $33 in two hours —and exposed a major flaw** (The New Stack [devops]) — relevance 9/10
  Claude Fable 5.1 agents used Playwright to capture screenshots from specific camera positions and compare them against real-world photos for visual QA in a 3D city generation task, effectively detecting 'technically correct but still looked wrong' issues.
  Why: Crumbl-ops performs visual checks in its existing adversarial review system and could use a Playwright-based 'agent vision' technique for UI validation or other visual data points like rendered reports.

- **Codex bundles LibreOffice** (Simon Willison [ai_engineering]) — relevance 9/10
  OpenAI's Codex desktop app bundles full installations of LibreOffice, Python, Node.js, Poppler, and Git, using internal 'skills' to enable the LLM to access and utilize these binaries for various tasks, including document processing.
  Why: This suggests a concrete pattern for local tool use and document processing (e.g., using Poppler for PDF parsing) that could be integrated into crumbl-ops for non-invoice financial document extraction, leveraging its Python stack.

- **datasette-mcp 0.2** (Simon Willison [ai_engineering]) — relevance 9/10
  The datasette-mcp plugin updated its execute_sql output to an array of objects, making it easier for LLMs to interpret SQL query results by explicitly mapping elements to columns.
  Why: Crumbl-ops uses an MCP server for Claude to perform read-only QBO queries; this update directly improves the reliability and interpretability of SQL results for Claude.

- **Your AI provider can change the deal on you. Here's the 5-prompt audit I run to stay ready.** (Nate Jones [ai_strategy]) — relevance 9/10
  This post advises on maintaining 'provider independence' for AI services by regularly auditing the portability of accumulated 'working context' using a '5-prompt audit' and a '30-minute provider exit test' to prevent being locked in.
  Why: Crumbl-ops relies heavily on Claude Code for development and headless operations, making provider independence and portability of its 'working context' a critical strategic consideration for long-term 'scaling small-team engineering'.

## Recommendations

- [MEDIUM] Enhance Claude Code Subagent Memory and Session Persistence
  Implement `memory: project` (or `user`, `local`) for subagents within Claude Code development to provide persistent context, and leverage the `promptCacheTtl` setting for headless `claude -p` jobs. This will ensure subagents retain codebase facts and long-running `claude -p` sessions benefit from extended context caching.
  Inspired by: This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling; The systems guide to production token optimization; OpenAI will sell you Astra, but not the system that scored 98.6% on ARC-AGI-3; GPT-6 Astra’s score of 98.6% looked like AGI. Then researchers read the fine print.; How I turned Claude into a self-improving PM assistant | Daniel Blum (PM, Melio)
  Impact: Significantly improve Claude Code development session efficiency by reducing redundant 're-deriving codebase facts,' enable faster context loading for repeated tasks, and enhance performance for long-running headless `claude -p` jobs (e.g., month-end CFO narrative, weekly memory consolidation).
  Where it fits: Subagent configurations using a new `memory:` frontmatter entry under `.claude/agent-memory/`, and configuration of `promptCacheTtl` for headless `claude -p` jobs and developer sessions.
  First step: Identify a frequently used Claude Code subagent (e.g., for `skills/` development or documentation) and configure its frontmatter with `memory: project`, then compare its multi-session performance with a baseline.
  Risks: Increased local storage usage for memory files. Potential for stale or incorrect facts if memory is not appropriately curated or invalidated, requiring explicit invalidation mechanisms.

- [LARGE] Integrate Poppler for Non-Invoice Financial Document Extraction
  Develop a specialized Claude Code skill that orchestrates the use of a local Poppler installation (or a containerized Poppler instance available to Cloud Run) to perform text and layout extraction from *non-invoice* financial documents (e.g., bank statements, receipts, tax forms). The extracted raw text would then be fed to Claude for summarization or structured data extraction, carefully avoiding LLM use for deterministic vendor invoice parsing.
  Inspired by: Codex bundles LibreOffice; BREAKING: Perplexity Just Split the AI Agent in 2. The Cloud Reasons, Your Mac Keeps the Secrets.; Your Mac is now part of Perplexity’s AI infrastructure; CFO interest: LLMs for document extraction (invoices, statements, receipts, tax forms).
  Impact: Automate data ingestion and analysis for a new class of financial documents, reducing manual effort for the CTO/CFO and enabling more comprehensive reporting and audit capabilities beyond current deterministic invoice parsing.
  Where it fits: A new skill in `.claude/skills/` (e.g., `/extract-financial-doc`), a new Python module in `src/ops/financial_docs/` to wrap Poppler calls, and a Cloud Run service account with permissions for external PDF fetching. This would support 'Automated financial reporting and variance analysis' and 'AI-powered audit and reconciliation'.
  First step: Create a proof-of-concept Python script that uses `pypoppler` (or a similar wrapper) to extract text from a sample bank statement PDF and demonstrate the output to Claude Code for summarization, ensuring no LLM is involved in the initial *parsing* step.
  Risks: Complexity of setting up and maintaining a local/containerized Poppler instance. Potential for PII exposure if sensitive data is not properly handled during extraction and redaction. Need to ensure robust parsing and error handling for varied document layouts and careful definition of 'non-invoice' scope to avoid the explicitly rejected false premise.
