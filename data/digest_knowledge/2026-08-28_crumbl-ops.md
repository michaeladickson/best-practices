# Digest: crumbl-ops — 2026-08-28

## Top Posts

- **Shopify’s CEO threatened to ban Claude Code. Anthropic had already closed the feature request.** (The New Stack) — relevance 9/10
  Shopify's CEO highlighted a critical issue where Claude Code fails to recursively read project-level context files like AGENTS.md and local .agents/skills, leading to agents operating under inconsistent rules in large codebases. This 'split brain' problem causes inefficiencies for developers, despite attempts to automate workarounds.
  Why: crumbl-ops uses Claude Code as its primary development partner and has a complex context system (CLAUDE.md, knowledge/, .claude/rules/, skills/), making this issue directly impactful on Claude's efficiency and reliability in its monorepo.

- **Your AGENTS.md is a Neural Net** (Kun Chen (Kun's Field Notes)) — relevance 9/10
  The article critiques common problems with agent memory files like `AGENTS.md` (empty, bloated, stale, drifted) and proposes treating project-level memory like a neural net. It suggests setting a size budget and 'training' the context by analyzing past agent sessions to prune and consolidate rules, ensuring only relevant, active context is maintained.
  Why: crumbl-ops relies heavily on `CLAUDE.md`, `knowledge/`, and `.claude/rules/` for Claude Code context; this provides a concrete, technique-level approach to manage context bloat, staleness, and drift, directly enhancing Claude Code efficiency.

- **Anthropic’s new Files API vs. pasting: It will save you time, but it won’t save you money.** (The New Stack) — relevance 9/10
  Anthropic's new Files API allows developers to upload documents once and reference them by ID in subsequent requests, streamlining setup compared to pasting. While it improves workflow and context management, testing showed it doesn't significantly reduce token count or cost, in contrast to prompt caching which can save tokens.
  Why: crumbl-ops uses Claude Code extensively and manages significant context; evaluating the Files API for efficient context handling, especially alongside existing prompt caching strategies for headless `claude -p` jobs, is directly actionable for making Claude Code sessions more efficient.

- **Perplexity just separated reasoning from authority. Here’s why it matters for enterprises.** (The New Stack) — relevance 9/10
  Perplexity's Portable Computer architecture separates the probabilistic reasoning of an AI model from the deterministic authority of the execution harness. The model proposes actions, but deterministic software (a loop controller) enforces policies and validates tool calls within an OS-level sandbox before execution, enhancing security and reliability.
  Why: crumbl-ops is interested in 'AI agents for operations' and has 'prompt-injection hardening' and 'financial-agent guardrails'; adopting this 'reasoning from authority' pattern with a deterministic harness could significantly strengthen the reliability and security of its headless `claude -p` jobs.

- **Aider, Claude Code, and OpenClaw ran an identical model. Token use varied 70-fold.** (The New Stack) — relevance 9/10
  Recent benchmarks across various AI coding agents show that the 'harness'—the software steering the model—can impact token usage and cost as much as the model itself, with observed variations up to 70-fold. This highlights the critical importance of optimizing harness design and context management for token efficiency.
  Why: crumbl-ops extensively uses Claude Code and headless `claude -p` for various jobs; understanding and optimizing the agent harness for token efficiency is directly actionable for 'making Claude Code sessions more efficient' and managing implicit costs, even with a flat Max subscription.

## Recommendations

- [MEDIUM] Optimize Claude Code Context Hierarchy
  Develop a hierarchical context loading mechanism for Claude Code and `claude -p` jobs that dynamically assembles the prompt context based on the current working directory. Prioritize local `.claude/rules/` and `.claude/skills/` over global `CLAUDE.md` and the `knowledge/` system. Implement a 'context budget' for frequently-accessed rules and a script to flag stale or low-impact rules for pruning, informed by agent session logs.
  Inspired by: Post 74: Shopify’s CEO threatened to ban Claude Code. Anthropic had already closed the feature request.
Post 115: Your AGENTS.md is a Neural Net
  Impact: Significantly improves the efficiency and accuracy of Claude Code sessions by ensuring agents receive precise, relevant context, reducing 'split brain' issues and context bloat. This will lead to faster and more reliable development and autonomous operational tasks.
  Where it fits: Current `.claude/rules/`, `CLAUDE.md`, `knowledge/` structures, and the internal tooling/scripts that manage Claude Code's invocation and context assembly for interactive and headless sessions. Specifically affects development workflows and scheduled jobs like 'weekly memory consolidation' and 'monthly knowledge curation'.
  First step: Develop a Python script that simulates how Claude Code would receive context based on a mock current working directory, parsing the existing `CLAUDE.md`, `knowledge/`, `.claude/rules/`, and `.claude/skills/` to identify potential conflicts, redundancies, or missing context due to non-hierarchical loading.

- [LARGE] Implement Deterministic Agent Action Guardrails
  Enhance the AI agent execution environment (especially for headless `claude -p` jobs) by integrating a deterministic 'shell judge' layer. This layer would use Abstract Syntax Tree (AST) parsing for shell commands and a configurable allowlist/denylist for tool calls and file system operations, explicitly sanctioning or denying agent-proposed actions *before* they are executed. This separates probabilistic agent reasoning from deterministic execution authority.
  Inspired by: Post 71: Perplexity just separated reasoning from authority. Here’s why it matters for enterprises.
Post 5: Breaking Claude Code Opus 5 Auto Mode
Post 22: LM Studio built a judge for AI commands. Then the judge started agreeing with the defendant.
  Impact: Dramatically increases the security and reliability of AI agents by preventing malicious or unintended commands from executing, even if prompt injection bypasses model-level defenses. Reduces risk of data corruption or unauthorized access in automated workflows for 'month-end CFO/controller narrative' and other scheduled jobs.
  Where it fits: Scripts invoking `claude -p` (e.g., in cron jobs), potentially within the FastAPI application if agents call shell commands, and integrating with `src/ops/secret_redaction.py` for a more holistic prompt-to-action security chain. This is an *application-layer* hardening, distinct from generic Cloud Run sandboxes.
  First step: Prototype a Python module that takes a proposed shell command string from an agent, uses `shlex.split` and `ast` (or a more specialized shell parser) to parse it, and then checks the parsed command against a simple, hard-coded allowlist of safe commands and arguments. Log any disallowed commands without executing them.
