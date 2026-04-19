# Digest: crumbl-ops — 2026-04-19

## Top Posts

- **Claude Cowork 101: How to automate your workday without touching code | JJ Englert (Tenex)** (Lenny's Newsletter [product]) — relevance 10/10
  This tutorial provides a deep dive into Claude Cowork, covering project setup, creating "brain" files for consistent persona, integrating with apps like Gmail and Slack via one-click connectors, and building scheduled tasks. It emphasizes leveraging shared memory and agent permissions for robust automation. This offers highly actionable strategies for the crumbl-ops CTO to enhance Claude Code efficiency, personalize its behavior, and automate specific operational workflows like email debriefs or Slack interactions.
  Why: This offers highly actionable strategies for the crumbl-ops CTO to enhance Claude Code efficiency, personalize its behavior, and automate specific operational workflows like email debriefs or Slack interactions.

- **Changes in the system prompt between Claude Opus 4.6 and 4.7** (Simon Willison [ai_engineering]) — relevance 10/10
  Details Anthropic's system prompt changes for Claude Opus 4.7, highlighting new desktop integration tools (Chrome, Excel, Powerpoint agents) and an emphasis on Claude acting rather than clarifying when minor details are unspecified. It also notes efforts to make Claude less "pushy." Understanding these changes is crucial for optimizing interactions and improving development efficiency.
  Why: As Claude Code is the primary development partner, understanding these system prompt changes is crucial for optimizing interactions, improving development efficiency, and potentially exploring new AI-powered integrations for operational workflows.

- **The impact of AI on software engineers in 2026: key trends** (The Pragmatic Engineer [engineering]) — relevance 10/10
  A survey of software engineers reveals key trends like rising AI tool costs, frequent usage limits, increased technical debt from "AI slop," and shifting roles towards orchestration and context switching. It highlights that AI accelerates output but introduces new challenges for quality and management. This provides critical insights for managing Claude Code costs and mitigating technical debt.
  Why: This provides critical insights for the CTO on managing Claude Code costs, mitigating technical debt ("AI slop"), adapting engineering leadership strategies for AI-accelerated development, and maintaining quality with a small team.

- **When AI writes 100K lines of code, QA becomes the whole job** (The New Stack [devops]) — relevance 10/10
  This post argues that AI-accelerated code generation shifts the software development bottleneck from writing code to validating it, making QA the primary focus. It underscores the challenge of dealing with "buggy but functional code" and the need for new operational approaches in quality assurance. This is directly relevant to crumbl-ops' strategy of using Claude Code for all development, emphasizing the urgent need for robust AI-driven testing.
  Why: This is directly relevant to crumbl-ops' strategy of using Claude Code for all development, emphasizing the urgent need for robust AI-driven testing, automated test generation, and quality gates to manage the validation bottleneck.

- **As agentic AI explodes, Amazon doubles down on MCP** (The New Stack [devops]) — relevance 10/10
  Discusses the Model Context Protocol (MCP) as the de facto method for connecting AI agents to tools and data, with AWS actively extending it to support "always-on" and event-driven agents through webhooks and notifications. This validates crumbl-ops' existing MCP usage and points to future agentic capabilities, directly supporting operational automation.
  Why: crumbl-ops already uses an MCP server for QBO; this validates the current strategy and provides a roadmap for evolving to more sophisticated, "always-on" AI agents for automating core operational workflows.

## Recommendations

- [MEDIUM] Develop and standardize "Brain Files" and "Skills" for Claude Code using a shared knowledge base (e.g., a dedicated Git repository). This would encapsulate common prompt patterns, project context, and specific business rules for development and operational tasks, similar to the "brain" file strategy discussed for Claude Cowork.
  Inspired by: Claude Cowork 101 (Post 76), Changes in Claude System Prompt (Post 5), Adding a new content type (Post 7)
  Impact: Significantly improve Claude Code session efficiency, ensure consistency across development tasks, and potentially reduce token consumption by providing optimized context and memory.

- [LARGE] Proactively design and implement an AI-driven Quality Assurance (QA) and security testing framework. Focus on automating test generation, property-based testing, and fuzzing, alongside robust API contract testing, given that Claude Code generates all code. Integrate continuous drift detection for APIs.
  Inspired by: When AI writes 100K lines of code, QA becomes the whole job (Post 64), Agents are rewriting the rules of security (Post 63), SmartBear’s Swagger update (Post 4), RIP Pull Requests (Post 26)
  Impact: Critically maintain software quality and security at AI-accelerated development speeds, reduce human engineer burden in validation, and prevent technical debt from "AI slop."

- [MEDIUM] Explore "Computer Use" agents to automate operational workflows lacking robust APIs, such as vendor invoice submission portals (Sysco, US Foods PDFs → QBO bills) or specific functions within When I Work. Prioritize high-volume, repetitive tasks that currently require manual UI interaction to start.
  Inspired by: Hugging Face pushes into “computer use” (Post 32), OpenAI’s superapp is taking shape (Post 35), Headless everything for personal AI (Post 1), How to prepare for agentic ITops (Post 19)
  Impact: Automate previously unautomable workflows, significantly reducing manual labor for the owner/operator, and improving overall operational efficiency and accuracy in data entry.

- [MEDIUM] Implement a monitoring and cost tracking system for Claude Code token consumption, categorizing usage by project/feature. Alongside this, establish "AI-aware" architectural and code review principles to guide Claude Code towards concise, efficient solutions and actively manage "AI slop" to prevent excessive technical debt.
  Inspired by: The Pulse: ‘Tokenmaxxing’ (Post 27), The impact of AI on software engineers (Post 70), Quoting Bryan Cantrill (Post 74)
  Impact: Gain control over AI-related operational costs, ensure sustainable growth and maintainability of the codebase, and proactively address the accumulation of technical debt inherent in AI-accelerated development.
