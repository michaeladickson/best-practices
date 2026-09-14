# Digest: crumbl-ops — 2026-09-11

## Top Posts

- **This week in Claude Code (2026-08-28): /resume on desktop, phone-started sessions, subagent memory, cost tooling** (Claude Code weekly newsletter (email)) — relevance 9/10
  The Claude Code weekly update introduces features for session mobility, cost/usage tooling (e.g., persistent subagent memory, `promptCacheTtl`), enhanced permissions and safety (e.g., `claude --restricted` mode, editable auto-mode rules), and new workflow patterns like the `/recap` skill.
  Why: This directly impacts Claude Code efficiency, agent memory management, and security for crumbl-ops' existing `claude -p` headless jobs and development workflows, aligning with key project goals.

- **Stop AI code sprawl before it destroys your software design** (The New Stack [devops]) — relevance 8/10
  AI-generated code can lead to "Comprehension Debt" by violating architectural boundaries, even if functionally correct; the article advocates for "Executable Architecture" using Python tools like `pytest-archon` and CI/CD to enforce design and maintain system mental models.
  Why: Addresses technical debt and code quality for AI-generated code, highly relevant to crumbl-ops' use of Claude Code for all development and its goal of technical debt management.

- **OpenAI gave an AI the power to block its own engineers’ code** (The New Stack [devops]) — relevance 8/10
  OpenAI has implemented an AI-powered security review system that can automatically block code merges if vulnerabilities are detected, alongside using "superhuman" AI models for general code review, regression detection, and dependency management.
  Why: Provides a concrete, advanced implementation target for enhancing crumbl-ops' existing AI code review (PR Review Gate) and AI-driven testing/QA for security.

- **Quoting Boris Cherny** (Simon Willison [ai_engineering]) — relevance 8/10
  Boris Cherny emphasizes that AI-written code needs higher scrutiny, highlighting guardrails like extensive linting, various tests (E2E, fuzzers), automated code reviews, and refactoring used at Anthropic.
  Why: Reinforces the importance of crumbl-ops' existing AI-driven QA and code review, and suggests specific techniques like Claude-driven E2E tests and fuzzers to augment the current framework.

- **Researchers found that 1 in 5 MCP access policies came back broken or missing** (The New Stack [devops]) — relevance 7/10
  Research on the Model Context Protocol (MCP) revealed significant security flaws, including authorization issues and prompt injection vulnerabilities where tool descriptions could be exploited to give agents unintended instructions.
  Why: Directly informs hardening crumbl-ops' existing 'MCP server for read-only QBO queries' and prompt-injection defenses for Claude's tool usage.

## Recommendations

- [SMALL] Refine Claude Code Sessions with Persistent Memory and Restricted Mode
  Leverage Claude Code's new persistent memory feature for subagents to enhance `knowledge/` and `CLAUDE.md` agents, reducing context redundancy. Additionally, enable the `claude --restricted` mode for `llm_eval` harness runs and potentially critical headless `claude -p` jobs (e.g., in `scripts/`) to bolster agent security and control.
  Inspired by: Post 143 (Claude Code weekly newsletter) and Post 124 (Coop – Isolated VM Environments for Running Claude Code and Codex)
  Impact: Increased Claude Code session efficiency by reducing repetitive context loading, improved autonomy for long-running `claude -p` jobs, and enhanced security for automated testing and critical operations.
  Where it fits: `.claude/skills/`, `knowledge/`, `CLAUDE.md`, `tests/fixtures/llm_eval/`, and `scripts/` that run headless `claude -p` jobs.
  First step: Experiment with adding `memory: project` to a new subagent in `.claude/skills/` and observe its impact on context loading and task completion time. Simultaneously, test `claude --restricted` on a non-critical `llm_eval` run.
  Risks: Potential for unexpected behavior or misconfigurations when introducing new agent memory patterns or restrictive modes, requiring careful testing. The `claude --restricted` mode might initially prevent valid agent actions if not configured properly, requiring iteration.

- [MEDIUM] Implement AI-Assisted Executable Architecture in CI/CD
  Integrate architectural validation into the existing CI/CD pipeline using a Python-based tool like `pytest-archon`. Claude Code can assist in defining and maintaining these architectural rules, ensuring that AI-generated code adheres to `crumbl-ops`'s established design principles and preventing 'Comprehension Debt'. This expands upon the existing `llm_eval` harness and PR Review Gate.
  Inspired by: Post 64 (Stop AI code sprawl before it destroys your software design), Post 68 (OpenAI gave an AI the power to block its own engineers’ code), and Post 7 (Quoting Boris Cherny)
  Impact: Maintains architectural integrity and reduces technical debt caused by AI-generated code, enhances the robustness of the automated code review process, and provides early detection of design violations, freeing up human engineers for higher-level architectural oversight.
  Where it fits: The `llm_eval` pytest suite (e.g., `tests/test_model_strings_pinned.py`), a new `tests/architecture/` directory, and the CI/CD pipeline triggering the `llm_eval` marker.
  First step: Research and select a Python architectural testing tool (e.g., `pytest-archon`). Task Claude Code to draft initial architectural rules for a core module (e.g., `src/ops/`) and integrate a basic `pytest-archon` test into the existing `llm_eval` suite.
  Risks: Initial overhead in defining comprehensive architectural rules; false positives in architectural tests might slow down development initially; ensuring Claude accurately generates and updates `pytest-archon` rules requires careful prompt engineering and validation.
