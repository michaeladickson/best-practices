---
verified: 2026-03-28
source: Learn and Grow Rich — AI CFO Playbook by Zach Oehlman (LinkedIn / Notion)
---

# AI CFO Playbook — Reference

External playbook describing 5 MCP-connected Claude workflows for SMB financial intelligence. Useful as a feature checklist for CrumblOps Financial Pulse and future CFO-layer capabilities.

## Their 5 Modules vs CrumblOps

| Their Module | What It Does | CrumblOps Status |
|---|---|---|
| Cash Flow Forecaster | 90-day 3-scenario forecast (best/base/worst) from QBO P&L + AR/AP | **Built** (monthly). Gap: need daily cash flow forecast with known payment dates (payroll, SBA, Crumbl deposits). |
| Margin Leak Detector | Cross-reference Stripe revenue × QBO expenses by service line, flag >2% margin drops | **Built** (P&L cost drivers, food/labor % by store). Gap: proactive alerting when metrics drift. |
| Tax Planning Copilot | Quarterly estimated tax, entity structure optimization, deduction acceleration | **Not built**. Low priority — Gusto handles payroll tax, CPA handles entity. |
| AR Enforcer | Aging buckets, auto-draft collection emails, Slack alerts for past-due | **N/A** — Crumbl is cash/card POS, no AR. Could be relevant for Taggart's landscaping business (commercial contracts). |
| Weekly Financial Pulse | 5-metric snapshot: cash, revenue, expenses, AR, gross margin | **Gap** — this is the Financial Pulse on our roadmap. Ours will be daily and proactive (AI-generated), not a manual prompt. |

## Key Difference: Their Approach vs Ours

They describe **100 manual prompts** you copy-paste into Claude/Cowork with your data. Each run is ephemeral — no memory, no tracking, no automation.

CrumblOps has the data layer, analytics engine, and automation already built. The gap is the **proactive intelligence layer** — a system that watches everything and surfaces what matters without being asked.

## Features Worth Adding (from their playbook)

1. **Daily cash flow forecast** — not just monthly. Know exact cash position on specific dates when payroll hits, SBA payment clears, Crumbl deposits arrive. 13-week rolling view.
2. **Financial Pulse** — daily AI briefing: cash position, margin trends, labor targets, revenue anomalies, OE flags. Delivered via email/Slack before the owner opens their laptop.
3. **Variance explanations** — not just "labor was high" but "labor was high because Richmond had 3 unplanned call-outs on Thursday"
4. **Price/cost alert** — vendor price changes detected from invoice parsing, flagged immediately
5. **Exit readiness** (Phase 4) — EBITDA multiple estimates, QoE prep, working capital peg calculation, customer concentration check. Relevant for Crumbl expansion + Taggart relationship.

## Their Level Structure (for reference)

- Level 1: Financial Clarity (know your numbers) — P&L translation, unit economics, break-even
- Level 2: Cash Flow & Survival — 13-week forecast, payroll stress test, burn rate, runway
- Level 3: Profit & Pricing — margin by product line, price elasticity, vendor negotiation
- Level 4: Reporting — monthly close checklist, variance analysis, executive dashboards
- Level 5: Exit Readiness — EBITDA multiples, SDE, DCF, data room structure, QoE prep
