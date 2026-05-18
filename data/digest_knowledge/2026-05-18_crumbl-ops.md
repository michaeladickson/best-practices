# Digest: crumbl-ops — 2026-05-18

## Top Posts

- **Executive Briefing: Stop asking if AI can do this. Start asking what shape the work is.** (Nate Jones [ai_strategy]) — relevance 10/10
  This briefing re-frames AI investment from 'can AI do it?' to 'what shape is the work?', offering a six-dimension framework to decide whether to automate, build, buy, hire, or wait. It highlights that AI investment is a capital allocation problem with wide upside/downside variance, and misclassifying work leads to significant costs and missed opportunities.
  Why: As both CTO and CFO, the owner of crumbl-ops makes strategic capital allocation decisions for engineering and finance workflows; this post provides a critical framework for evaluating and prioritizing AI initiatives.

- **Spec-driven development: The AI engineering workflow at Notion | Ryan Nystrom** (Lenny's Newsletter [product]) — relevance 10/10
  This outlines Notion's 'spec-first development workflow' where AI agents (like Codex) are used to format dictated ideas into specs, then autonomously implement and verify the code. It emphasizes the criticality of fast CI in this AI-driven development paradigm and how engineers can prompt agents to defend their reasoning.
  Why: Crumbl-ops uses Claude Code for all development, and this provides a concrete, advanced workflow to boost Claude Code session efficiency, ensure AI-driven testing/QA, and maintain quality with a small engineering team.

- **Anthropic splits billing again: Agent SDK gets separate credit pools** (The New Stack [devops]) — relevance 10/10
  Anthropic announced a change in billing where programmatic usage (e.g., Claude Agent SDK, Claude Code GitHub Actions, third-party apps) will draw from a separate monthly credit pool, distinct from interactive usage. Unused credits expire, and exceeding credits reverts to pay-as-you-go API rates, making cost management more complex.
  Why: Crumbl-ops uses Claude Code as its primary development partner and Claude for review, meaning programmatic usage and associated costs are critical for the owner/CFO to monitor and manage, directly impacting budgets and engineering efficiency.

- **The clean-up cost of AI-generated code is what the velocity narrative leaves out** (The New Stack [devops]) — relevance 10/10
  This article warns that the rapid generation of AI code, while increasing velocity, comes with hidden cleanup costs and can lead to significant technical debt if not properly managed. It highlights the challenge for engineering organizations to maintain quality and avoid accumulating unmanageable code.
  Why: With Claude Code used for 'all development' in crumbl-ops, managing the quality and potential technical debt of AI-generated code is a paramount concern for engineering leadership, directly impacting long-term maintainability and scaling efforts.

- **Your AI agent is rediscovering 85% of its context every run. Here's the architecture fix (+ Contract Spec, Failure Triage, and Stack ADR)** (Nate Jones [ai_strategy]) — relevance 10/10
  This post identifies a common failure mode for AI agents: inefficient context retrieval (RAG). It argues for moving beyond simple vector search to a more comprehensive 'knowledge layer' architecture that assembles all necessary context (records, permissions, policies, prior decisions, provenance) to ensure agents act reliably and avoid costly errors.
  Why: Crumbl-ops relies on Gemini for invoice extraction and email classification, and Claude for demand forecasting and weekly reviews; these agents need accurate, specific context, and improving their context management is crucial for efficiency and reliability.

## Recommendations

- [MEDIUM] Evaluate AI Initiatives with "Work Shape" Framework
  Apply a structured framework, like the one suggested in 'Stop asking if AI can do this. Start asking what shape the work is.', to rigorously evaluate new AI automation initiatives across both engineering and finance. Categorize workflows based on repeatability, cost of error, judgment required, and model volatility to determine whether to automate, build, buy, hire, or wait.
  Inspired by: Post 5 (Executive Briefing: Stop asking if AI can do this. Start asking what shape the work is.), Post 51 (Six things have to be true before AI changes a workflow.), Post 77 (The most-requested thing in 98K inboxes about AI).
  Impact: Ensures optimal capital allocation for AI, prevents costly misapplications of AI, and clarifies which workflows are truly ripe for automation versus needing human oversight. Directly addresses both CTO and CFO strategic interests.
  Where it fits: Strategic planning for all new feature development and process automation (e.g., new acquisition integration, expansion of inventory, payroll, or accounting features).
  First step: Define a lightweight 6-dimension scoring framework (e.g., repeatability, cost of mistake, judgment, market maturity, company specificity, model stability/rate of change) for 2-3 existing or planned crumbl-ops AI workflows (e.g., payroll processing, production planning adjustment, new vendor invoice parsing) and document the decision rationale.
  Risks: Initial overhead in defining the framework, potential for analysis paralysis, resistance to objective evaluation if prior assumptions are challenged.

- [LARGE] Centralize Claude Code Skills & Adopt Spec-Driven AI Development
  Establish a centralized, version-controlled library for Claude Code skills and coding standards, as suggested in 'How to build a skills library for your engineering team.' Complement this by implementing a 'spec-driven development' workflow using Claude Code, where specifications are generated/refined by AI, and then the agent implements and verifies against them with fast CI, as seen in Notion's example. Actively monitor Claude's programmatic usage costs (Agent SDK) based on Anthropic's new billing structure.
  Inspired by: Post 110 (Spec-driven development: The AI engineering workflow at Notion), Post 87 (How to build a skills library for your engineering team), Post 19 (The clean-up cost of AI-generated code is what the velocity narrative leaves out), Post 62 (Anthropic splits billing again: Agent SDK gets separate credit pools).
  Impact: Significantly improves Claude Code session efficiency and consistency, reduces AI-generated technical debt, enhances AI-driven testing/QA, maintains code quality with a small team, and provides clear visibility into AI development costs.
  Where it fits: `CLAUDE.md`, `knowledge/`, `system/`, `skills/` directories, CI/CD pipeline, `Engineering` and `Finance` (for cost tracking).
  First step: Create a Git repository for core Claude Code 'skills' (e.g., coding standards, testing patterns, Cloud Run deployment best practices) and integrate it into the Claude Code development environment so it's easily accessible and versioned. Simultaneously, review current Claude API usage to establish a baseline for programmatic vs. interactive costs.
  Risks: Initial investment in skill definition and workflow changes, potential for developer friction if not clearly communicated, ongoing maintenance of skill library. Ignoring cost implications could lead to unexpected bills.

- [LARGE] Implement Intelligent Knowledge & Oversight Layers for Operational AI Agents
  Evolve Crumbl-ops' AI agent architecture beyond simple RAG (e.g., for Gemini invoice/email) to include a comprehensive 'knowledge layer' that intelligently assembles all relevant context (data, permissions, policies, previous decisions) for each agent run, preventing costly context rediscovery. For agents making critical decisions (e.g., payroll, invoice payments, production planning), design and implement a 'judge layer' to evaluate proposed actions and provide explicit approval or rejection, ensuring trust and mitigating risks.
  Inspired by: Post 66 (Your AI agent is rediscovering 85% of its context every run.), Post 103 (You gave your AI agent real tools. Here's the 4-part control layer it's missing + the Judge Layer implementation guide), Post 84 (Why agent harnesses fail inside cloud-native systems).
  Impact: Greatly increases the reliability, accuracy, and safety of operational AI agents, reduces errors in critical financial and operational workflows, and builds trust in autonomous systems. Directly supports automated financial reporting, payroll compliance, and anomaly detection.
  Where it fits: `AI` components (Gemini integrations), `Financial Workflows` (AP, Payroll), `Production Planning`, `Dual-model weekly review system`.
  First step: Select one high-impact agent (e.g., Gemini for invoice extraction) and map out all necessary context elements it *should* have for a perfect run (vendor terms, historical patterns, approval limits). Design a prototype 'knowledge assembly' module that fetches and presents this context to the agent before it acts. In parallel, for a high-risk automated decision (e.g., flagging an invoice for payment), outline the criteria for a human 'judge' to review before any action is taken.
  Risks: Increased architectural complexity, initial development time, potential for false positives/negatives in judge layer requiring human intervention, maintaining up-to-date knowledge layer components.

- [MEDIUM] Automate Financial Reporting & Audit with AI Skills
  Leverage AI, potentially through custom Claude skills (similar to those for financial filings), to automate complex financial reporting, variance analysis, and reconciliation tasks. Focus on creating agents that can compare data across multiple entities and time periods, identify discrepancies, and generate 'variance bridges' or 'model checks.' Integrate these tools with existing data (PostgreSQL, QBO API) to provide real-time dashboards and support AI-powered audit workflows, reducing manual effort in month-end close and multi-entity consolidation.
  Inspired by: Post 11 (How to compare 10 years of filings in minutes with AI), Post 97 (How finance teams use Codex), Post 2 (Automation’s promise: Distinguishing what delivers and works in the agentic age).
  Impact: Significantly reduces manual effort and error in financial closing and reporting, provides deeper insights into variances, accelerates audit processes, and enhances real-time financial visibility. Directly addresses key CFO interests.
  Where it fits: `Financial Workflows` (Month-end accruals, reconciliation, multi-entity reporting, variance analysis), `Reporting`. Integrates with QuickBooks Online API.
  First step: Identify one specific, recurring month-end reporting task (e.g., comparing actuals to budget for a key P&L line item across multiple stores) and prototype a Claude skill that can ingest the relevant data from PostgreSQL or QBO, perform the comparison, and highlight key variances. Validate results manually for the initial runs.
  Risks: Data quality dependencies, need for careful validation of AI-generated insights, potential for 'hallucinations' if not grounded in precise data and rules, integration complexity with QBO API.
