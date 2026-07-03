# Digest: command-center — 2026-07-03

## Top Posts

- **Apple just turned Safari into something AI agents can control** (The New Stack) — relevance 9/10
  Apple's Safari Technology Preview now includes a built-in Model Context Protocol (MCP) server, offering 16 tools for AI agents to directly interact with a live browser. Agents can capture screenshots, inspect the DOM, execute JavaScript, monitor network requests, and more, enabling sophisticated web automation without leaving the terminal.
  Why: This directly enables the 'Computer use agents for portals without APIs (tax, school, compliance)' interest by providing a robust, officially supported pathway for agents to interact with web interfaces.

- **Why traditional CI/CD fails for LLMs (and the release gates we built to fix it)** (The New Stack) — relevance 9/10
  Traditional CI/CD is inadequate for probabilistic LLM systems due to gradual performance degradation and distribution shifts that don't trigger hard failure thresholds. The article advocates for new release gates, including baseline evaluations, drift detection, shadow validation, and cost/latency guardrails to prevent silent AI regressions.
  Why: Crucial for 'Agent decision quality: classification accuracy, prompt regression, fixture-based testing' for command-center's agents, offering methods to ensure reliability beyond simple pass/fail checks.

- **Run this 4-question test before you let any AI into your files, your Slack, or your phone.** (Nate Jones [ai_strategy]) — relevance 9/10
  This post emphasizes a critical 4-question test to assess the risks before integrating AI agents with sensitive areas like files, communication channels (Slack), or personal devices. It stresses the importance of establishing trust and explicit boundaries before granting AI agents extensive context access.
  Why: Provides a practical framework for implementing 'Prompt injection defenses for user-controlled inputs' and general security considerations for high-stakes outputs like the 'Sara digest' and 'iMessage monitor'.

- **Fable's judgement** (Simon Willison [ai_engineering]) — relevance 9/10
  This post describes a strategy for Claude Code users to optimize costs by having Fable use its judgment to delegate coding tasks to lower-power subagents (e.g., Sonnet or Haiku). High-level judgment and synthesis remain with the main model, while routine coding is offloaded, with this delegation strategy stored in a memory file.
  Why: Offers a direct, actionable strategy for 'Token efficiency for long-running agent ecosystems' within command-center's development using Claude Code, and hints at 'Brain files / skills library' structures.

- **“The harness is where the hard work is”: Harness bets on agents that enterprises can trust in production** (The New Stack [devops]) — relevance 9/10
  Harness's new Autonomous Worker Agents replace fixed scripts in CI/CD with reasoning AI agents, under existing governance and audit controls. The CEO emphasizes that building an agent is easy, but creating the 'harness'—the reliable, auditable, and controlled environment for production agents—is the true challenge.
  Why: Directly informs 'Multi-agent orchestration and shared memory between scheduled agents' and 'Observability for agent fleets' by highlighting the critical need for a robust 'harness' design to ensure trust and reliability for command-center's automated tasks.

## Recommendations

- [LARGE] Implement Web Automation for Portals via MCP
  Integrate Safari's new MCP server and/or explore AWS WorkSpaces for Agents to build robust 'computer use agents' for portals without APIs (e.g., tax, school, compliance). Focus on extracting structured data and enabling controlled interactions.
  Inspired by: Post 12: Apple just turned Safari into something AI agents can control; Post 77: AWS launches a desktop for agents; Post 2: Build the AI rig that turns your denial and tax pile into cited packets.
  Impact: Significantly expands automation capabilities for critical personal/professional tasks currently requiring manual web interaction, reducing cognitive load and time spent.
  Where it fits: New 'spoke' module (e.g., 'portal-automator') within the command-center ecosystem, leveraging existing Python stack for scripting and orchestrating browser interactions.
  First step: Experiment with Safari Technology Preview's MCP server (or a local Playwright setup similar to shot-scraper) to automate a simple, read-only data extraction task from a non-API web portal (e.g., login, navigate, copy table data).
  Risks: Complexity of maintaining browser automation (DOM changes), potential for CAPTCHAs/anti-bot measures, and the need for robust error handling and monitoring for autonomous web agents.

- [MEDIUM] Build an 'Eval-First' Agent Quality & Observability Loop
  Adopt an 'eval-first workflow' for all command-center agents. Implement continuous evaluation using frameworks like DSPy for prompt regression and accuracy, incorporate drift detection for classification models, and consider recording video demos (shot-scraper) for computer use agents to monitor performance and provide observability.
  Inspired by: Post 33: Why traditional CI/CD fails for LLMs; Post 9: Set a metric. Walk away. Let the agent optimize overnight; Post 17: Using DSPy to evaluate and improve Datasette Agent's SQL system prompts; Post 48: Sonnet 5 review: I ran 64 generations to find out if it's worth it; Post 90: How Gusto built a new product line with Claude Code; Post 60: Have your agent record video demos of its work with shot-scraper video.
  Impact: Ensures high-quality, reliable, and predictable outputs from all agents, preventing 'silent regressions' and improving trust. Provides clear insights into what agents are doing and why.
  Where it fits: Core 'agent_qa' module for all agents (email triage, meeting debriefs, Sara digest, iMessage monitor), integrated with existing scheduled Python agents and GitHub Issues for feedback.
  First step: Select one existing Gemini-powered agent (e.g., email classification) and build a simple, repeatable fixture-based test set. Use Claude Code to help draft initial evaluation scripts and a prompt that allows Gemini to self-evaluate its classification against known labels.
  Risks: Requires ongoing maintenance of evaluation datasets and metrics, potential for 'reward hacking' if evals are too simplistic, and initial overhead in setting up robust test harnesses.

- [MEDIUM] Formalize Tiered Model Routing & Token Efficiency
  Develop a formalized strategy for multi-model routing within command-center, explicitly defining when to use Claude Fable (for complex dev/synthesis), Claude Sonnet (for substantial implementation/reasoning), Gemini (for classification/debriefs), or potentially cheaper open-source models for mechanical tasks. Implement this as a 'model-picker' agent or a configurable skill.
  Inspired by: Post 3: Fable's judgement; Post 16: Stop paying frontier prices for work a cheaper AI would crush; Post 40: What's new in Claude Sonnet 5; Post 71: The Real Reason AI Costs Keep Rising; Post 97: Cheap Intelligence Won’t Matter If Your Context Is Trapped; Post 89: GLM-5.2 review.
  Impact: Significantly reduces token costs while maintaining or improving agent performance by matching model capabilities to task requirements. Mitigates vendor lock-in by designing for model flexibility.
  Where it fits: Centralized 'agent_dispatcher' or 'model_router' component responsible for instantiating and directing tasks to the appropriate LLM, integrated across all scheduled agents and Claude Code workflows.
  First step: Document the current model usage and cost for two key agent tasks (e.g., email classification with Gemini, a specific Claude Code skill). Then, experiment with substituting a lower-cost alternative (e.g., Sonnet 5 for a Fable task in Claude Code, or a smaller local model for a simple text transformation) and compare performance/cost metrics.
  Risks: Increased complexity in agent orchestration, potential for performance degradation if models are mis-selected, and the need to manage API keys/access for multiple models.

- [MEDIUM] Design Explicit Human-in-the-Loop & Injection Defenses
  Integrate explicit human-in-the-loop review steps for all high-stakes outbound content (Sara digest, Slack replies) and any actions that modify external systems. Strengthen prompt injection defenses for all user-controlled inputs (emails, transcripts) by including clear anti-injection rules in system prompts and performing regular security checks.
  Inspired by: Post 83: Run this 4-question test before you let any AI into your files, your Slack, or your phone; Post 107: What happened after 2,000 people tried to hack my AI assistant; Post 56: Anthropic’s Claude Sonnet 5 system card; Post 37: You can build 80% of your own AI memory.
  Impact: Protects against unintended agent actions or compromised outputs, maintaining trust in command-center's automated communications and data integrity, especially crucial for Michael's personal context.
  Where it fits: Built into agent workflows for 'Sara digest,' 'daily briefing' (outbound aspects), and potentially 'iMessage monitor' for flagging actionable items. System-level hardening for all Gemini/Claude prompts.
  First step: For the 'Sara digest' agent, add a mandatory manual review step where Michael must explicitly approve the generated email content before it is sent. Simultaneously, update the system prompts for email triage and transcript debriefs with robust anti-prompt-injection instructions, similar to those tested in Post 107.
  Risks: Adds friction to automated workflows, requires diligent human review, and prompt injection defense is an ongoing cat-and-mouse game requiring continuous updates.
