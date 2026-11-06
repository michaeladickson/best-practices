# Digest: crumbl-ops — 2026-11-06

## Top Posts

- **Agent Harness: How I Built My Own Claude Code, Step by Step** (Paweł Huryn (The Product Compass)) — relevance 9/10
  This tutorial details building a custom Python "Mini Harness" for AI agents, including loops, tools, sessions, memory compaction, permissions with an AI judge, subagents, and MCP servers, demonstrating superior performance to standard Claude Code.
  Why: crumbl-ops uses Claude Code and has an existing evaluation harness; this post offers actionable, Python-based technical details to enhance its custom agent harness, improving Claude Code efficiency and strengthening AI-driven testing and authorization.

- **Raindrop simulates your agent’s world to catch what your changes break** (The New Stack) — relevance 9/10
  Raindrop's "Simulations" platform allows developers to reconstruct an agent's production environment, including its tools, APIs, and databases, to evaluate how changes to prompts, models, or tools affect agent behavior before deployment.
  Why: As crumbl-ops relies on AI agents for sensitive financial and operational tasks, simulating the production environment to test agent changes is a direct, advanced enhancement for its "AI-driven testing and QA" and ensuring stability of "AI agents for operations."

- **I broke a working agent seven ways. The metric I was watching caught two of them.** (The New Stack) — relevance 9/10
  This post emphasizes the limitations of high-level success metrics for AI agents, using an example where a silent model upgrade behind an unpinned alias led to critical, undetected behavioral changes on sensitive financial tasks, only discovered through manual, deep diagnostic checks.
  Why: crumbl-ops performs financial transactions and uses multiple LLMs with model string pinning; this highlights a critical vulnerability in monitoring underlying model versions and the need for deeper diagnostics for "observability" and "AI-powered audit" to detect subtle, high-impact agent behavior shifts.

- **Dharma Field Extractor: Any Document In, Structured Fields in JSON Out** (Hugging Face Blog) — relevance 9/10
  This post introduces Dharma Field Extractor, a specialized 2-billion-parameter model that efficiently extracts structured fields in JSON from any document image, outperforming larger frontier LLMs in cost and performance for this specific task without per-type fine-tuning.
  Why: crumbl-ops explicitly uses deterministic parsers for vendor invoices and avoids general LLMs for this; however, this specialized, cost-effective model for *any document type* could be a narrow implementation delta to handle non-standard receipts, new vendor forms, or unparsed statements, addressing the "LLMs for document extraction" interest without contradicting existing deterministic parsing.

- **AlloyDB Express: Instant, scale-to-zero PostgreSQL for developers and coding agents** (Google Cloud Blog) — relevance 9/10
  AlloyDB Express is a new PostgreSQL offering designed for developers and AI coding agents, featuring instant provisioning, automatic scale-to-zero when idle, built-in AI capabilities, enterprise security, and one-click upgrade to production.
  Why: crumbl-ops uses PostgreSQL and Claude Code for development, with an existing LLM eval harness. AlloyDB Express offers a transformative way to provide instant, isolated, and cost-effective PostgreSQL instances for "AI-driven testing and QA" and enhancing the efficiency of Claude Code sessions.

## Recommendations

- [MEDIUM] Implement Specialized LLM for Ad-Hoc Financial Document Extraction
  Develop a workflow in src/invoices/ or src/ops/ to integrate a small, specialized LLM (like Dharma Field Extractor) for extracting structured data (JSON) from previously unparsed or varied financial documents such as miscellaneous receipts, ad-hoc statements, or new vendor forms, complementing the existing deterministic vendor parsers.
  Inspired by: Post 91 (Dharma Field Extractor: Any Document In, Structured Fields in JSON Out), Post 115/116 (Building AI for Lawyers - Jacob Lauritzen, CTO of Legora), Post 156 (Build Your Own AI Legal Team in Claude)
  Impact: Significantly expands the scope of automated financial data extraction beyond known vendors, reduces manual data entry for varied documents, and provides structured input for accounting/AP, saving CFO/finance time. It also offers a potential fallback/verification layer for existing deterministic parsers if issues arise.
  Where it fits: src/invoices/ (for integrating new extraction capabilities), src/ops/ (for broader financial document processing), or a new src/docs_ai/ module. The extracted data would feed into existing accounting workflows.
  First step: Identify 2-3 common types of financial documents (e.g., ad-hoc receipts for reimbursements, statements from minor vendors) that are currently manually processed, which are *not* handled by src/invoices/vendors.py, and prototype using a small, specialized LLM to extract key fields (e.g., date, vendor, total, line items) into JSON.
  Risks: Initial integration effort for a new model type. Ensuring high accuracy on diverse, unstructured documents will require careful prompt engineering and potentially fine-tuning the specialized model (if open-source), or robust error handling and human review. Potential for hallucinations on novel document types, requiring a clear human-in-the-loop validation for financial postings.

- [LARGE] Simulate Production Environment for AI Agent Evaluation and Monitoring
  Extend the existing LLM eval harness to simulate agent interactions within a reconstructed, isolated production environment (including mocked external APIs and database states) to predict how changes to prompts, models, or tools will affect agent behavior before deployment. Simultaneously, implement deep diagnostic metrics to monitor for subtle, high-impact behavioral shifts in production, beyond high-level success rates.
  Inspired by: Post 66 (Raindrop simulates your agent’s world to catch what your changes break), Post 70 (I broke a working agent seven ways. The metric I was watching caught two of them.), Post 149 (Executive Briefing: Your AI Agent Can Pass Every Demo and Still Double-Credit a Customer. The 8 Tests to Run Before You Buy.), Post 158 (Five controls to set before you let an AI agent buy, pay, or cancel anything for you).
  Impact: Proactively identifies unintended agent behaviors (e.g., unauthorized transactions, incorrect data postings) caused by changes in dev or silent model updates, significantly reducing operational risk in financial workflows. Improves confidence in deploying agent updates and strengthens audit capabilities by providing more granular insight into agent decision-making. Enhances "AI-driven testing and QA" to catch edge cases that current evals might miss.
  Where it fits: tests/fixtures/llm_eval/ (for defining simulated environments and scenarios), existing llm_eval pytest marker (for running tests in these environments), and src/ops/ (for instrumenting deeper production-time behavioral metrics and alerts related to agent actions, especially those interacting with QBO).
  First step: For a critical financial workflow (e.g., daily accounting sync, payroll import validation), create a simulated production environment within the existing eval harness. Develop a "trap task" or "adversarial scenario" (e.g., attempting to double-post a journal entry, process a payroll with invalid hours) and run the agent in the simulated environment to observe its behavior and identify potential failure modes *before* changes are deployed.
  Risks: Complex to accurately replicate production environments and external API behavior. Developing comprehensive "trap tasks" requires significant domain expertise. Requires ongoing maintenance of simulated environments. Over-instrumentation could lead to alert fatigue if metrics are not carefully curated.
