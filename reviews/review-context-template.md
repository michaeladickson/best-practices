# Review Context — Read This First

Copy this to `.github/prompts/review-context.md` in your repo and fill in the specifics.
This file tells reviewers what to focus on and what to skip, dramatically reducing false positives.

---

## What This App Is
- [What it does, who uses it, how many users]
- [Public SaaS? Internal tool? Mobile app?]
- [Deployment: Cloud Run, Vercel, App Store, etc.]
- [Team size and composition]

## Future Direction
- [Where this is headed — helps reviewers judge what's worth flagging now]

## Threat Model
- **Attack surface**: [public endpoints? internal only? mobile app with server?]
- **Data sensitivity**: [what data is most important to protect?]
- **Availability requirements**: [critical uptime? or OK if down briefly?]
- **Biggest real risks**: [the 2-3 things that would actually hurt if they went wrong]

## Intentional Design Decisions (Do NOT Flag These)
- [List specific decisions reviewers will be tempted to flag]
- Example: "No ORM — raw SQL with parameterized queries is intentional"
- Example: "JWT in localStorage — known tradeoff, acceptable for internal tool"
- Example: "Inline styles in React — avoids build tooling complexity"
- [Reference issue numbers if tracked: "tracked in issue #36"]

## What Makes a Good Finding
- **Concrete**: points to a specific file and line, not "consider adding..."
- **Proportional**: the fix effort matches the actual risk for this app's scale
- **Not already tracked**: check existing-issues.md before reporting
- **Actionable by this team**: if the fix requires new infrastructure the team can't maintain, skip it

## What to Skip
- Generic best-practice advice not tied to a specific code issue
- Enterprise patterns disproportionate to the team/user size
- Performance concerns that only matter at 100x current scale
- Style preferences, naming opinions, or "add docstring" suggestions
- Anything listed in "Intentional Design Decisions" above
