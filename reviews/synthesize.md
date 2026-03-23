You are synthesizing two independent code reviews of the same codebase — one from Claude and one from Gemini. Your job is to produce a single, actionable issue.

## How the reviews were produced

**Gemini received the full source files** as a single concatenated snapshot without the ability to navigate the repo, run searches, or read config files not included. It may:
- Suggest enterprise-grade patterns disproportionate to the app's scale
- Miss cross-file context (e.g. a validation that exists in a shared module)
- Recommend architectural changes that are overkill

**Claude has full repository access** (can browse files, run searches, read configs) and should be treated as the more authoritative source when the two disagree on factual matters (e.g. "this function exists" vs "this function is missing").

## How to evaluate findings

For each finding, determine:
1. **Confirmed** — both models flagged it (highest confidence)
2. **Claude-only** — only Claude flagged it (likely valid since Claude has full context)
3. **Gemini-only** — only Gemini flagged it (validate carefully — may be based on incomplete context)
4. **Contradicted** — the models disagree (explain why and pick the right answer)

## Rules

- Deduplicate: if both models found the same issue with different wording, merge into one item
- Promote findings that both models agree on — these are most likely real
- **Actively reject** findings that:
  - Recommend solutions disproportionate to the app's scale and team size
  - Suggest adding infrastructure the team doesn't have capacity to maintain
  - Are generic best-practice advice not tied to a specific code issue
  - Miss existing mitigations that Claude can verify exist in the codebase
  - Duplicate or overlap with existing open issues (move to Dismissed with issue #)
- Demote or drop findings that are intentional design decisions (per review-context.md)
- Keep the severity from whichever model's assessment is more accurate
- Preserve file paths and line numbers from whichever report is more specific
- Use markdown checkboxes so items can be tracked

## Output format

- Executive summary (2-3 sentences)
- "Confirmed by Both Models" section (highest priority)
- "Additional Findings" section (single-model findings worth acting on)
- "Dismissed" section (brief list of rejected/false-positive findings from either model, with reason for dismissal)
- Each finding: file, line, severity, description, suggested fix, source (Claude/Gemini/Both)

Output ONLY the synthesized issue body, no title or preamble.
