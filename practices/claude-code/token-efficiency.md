# Token Efficiency (Claude Code)

Patterns for avoiding quota burns and context bloat. Based on Anthropic's April 2026 postmortem — some users burned weekly quotas in 1–2 days.

## Root Causes

### 1. Cache Misses
Default cache TTL dropped from 1h → 5 min. Every miss costs 10× more than a hit.

**What rebuilds the cache:** adding an MCP mid-session, swapping models (Opus ↔ Sonnet).

**Fixes:**
- Lock `--model` and your MCP set at session start — don't add tools mid-run
- Watch cache hit rate: healthy is ~90% on 5-min default, 97–99% on 1h TTL
- If hit rate drops, `/clear` for a fresh prefix
- API key users (not Pro/Max): set `ENABLE_PROMPT_CACHING_1H=1` for sessions that stretch over an hour (writes 2×, reads 0.1×)

### 2. Context Bloat
Claude Code system prompt + tools + MCP = ~34K before you type. Quality slips before 200K; 200K is enough.

**Env vars:**
```bash
CLAUDE_CODE_DISABLE_1M_CONTEXT=1      # disable 1M window
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80    # compact at 80% (200K)
```

**Session moves:**

| Move | When |
|------|------|
| `/clear` | New unrelated task |
| `/compact <what to keep>` | At 50% or after every task — don't wait for autocompact |
| `"spawn a subagent for X"` | Isolated window; only result returns |
| `Esc Esc` / `/rewind` | After a bad turn — don't "No, try B", it keeps the failure in context |

**Load lean:**
- Move rules to `skills/`, `rules/`, or referenced `.md` files (progressive disclosure)
- Disable unused MCP servers, tools, skills, plugins
- Reference `@research.md` instead of asking Claude to grep — maintain summary docs like `docs/design.md`, `docs/permissions.md`
- **Curate MCPs ruthlessly** — every tool from every connected MCP sits in your context every turn. Prefer narrow single-purpose MCPs over kitchen-sink ones. Audit with [`punkpeye/awesome-mcp-servers`](https://github.com/punkpeye/awesome-mcp-servers) and [`modelcontextprotocol/servers`](https://github.com/modelcontextprotocol/servers).
- **Install skills instead of describing them in CLAUDE.md** — a skill loads only when invoked; CLAUDE.md text is always loaded. Catalogs: [`anthropics/knowledge-work-plugins`](https://github.com/anthropics/knowledge-work-plugins), [`phuryn/pm-skills`](https://github.com/phuryn/pm-skills), [`travisvn/awesome-claude-skills`](https://github.com/travisvn/awesome-claude-skills).

### 3. Wrong Model / Effort
Default reasoning burns roughly 2× the tokens of `medium` effort. On simple work, the quality lift rarely shows.

**Routing in CLAUDE.md:**
```
Use Opus for: architecture decisions, complex debugging, multi-file refactors
Use Sonnet for: standard feature work, reviews, explanations  
Use Haiku for: simple lookups, formatting, file moves
```

Note: Opus 4.7 delegates to smaller models less often than 4.6 — you need to explicitly route.

**Effort levels:** `xhigh` (Opus default), `high`, `medium`, `easy`. Set per-prompt, not per-session.

**Route out:** Swap `ANTHROPIC_BASE_URL` to OpenRouter for 400+ models at lower cost:
```json
"ANTHROPIC_BASE_URL": "https://openrouter.ai/api"
```

### 4. Wrong Input Format
- Full screenshot ≈ 1,300 tokens
- One PDF page = 1,500–3,000 tokens
- Full HTML dumps are worse

**Fixes:**
- Use [`vercel-labs/agent-browser`](https://github.com/vercel-labs/agent-browser) instead of Chrome MCP (accessibility tree, not screenshots — 82% fewer tokens than Playwright MCP)
- For PDFs in repo: run `pdftotext`, not `Read` — Read rasterizes pages (~3K tokens each)
- For mixed-format docs (PDF, .docx, .pptx, .xlsx, images): [`microsoft/markitdown`](https://github.com/microsoft/markitdown) converts to clean markdown. Drop-in for invoice processing, contract review, anything beyond pure PDF.
- For large repos: [`tirth8205/code-review-graph`](https://github.com/tirth8205/code-review-graph) — AST map so Claude reads only affected files (6.8× fewer tokens on reviews)
- For one-shot repo analysis without spawning a session: [`mufeedvh/code2prompt`](https://github.com/mufeedvh/code2prompt) — turns a repo into a single prompt-friendly file with up-front token counts

## Spec Prompts

Write like a spec — file paths, expected I/O, constraints. Vague requests burn turns:

```
# Bad
"Fix the auth bug"

# Good  
"In src/auth/middleware.py:47, the token expiry check uses datetime.now() instead of
datetime.utcnow(). Fix it to use UTC. The test is in tests/test_auth.py:test_token_expiry."
```

## Monitoring

- **Measure:** `phuryn/claude-usage`
- **Monitor:** `Gronsten/claude-usage-monitor`
- **Cache stats:** platform.claude.com/usage/cache (API key only)

## Where Used

- Applicable to any Claude Code project
