---
name: wait-what
description: "Stop. That last message did not land: re-pitch it."
user_invocable: true
disable-model-invocation: true
---

Wait, I don't follow where you got to. Re-pitch that: add the context you skipped,
write in ASD-STE100 Simplified Technical English (short sentences, one idea each, plain
verbs, no stacked acronyms), and use this repo's own vocabulary from `CLAUDE.md` rather
than generic terms.

Re-explain what you already did. Do not re-run tools, redo the work, apologize, or
observe that the message was unclear. Just give the clearer version.

<!--
Ported from mattpocock/skills (MIT), skills/productivity/wait-what.
Adapted: upstream reads `CONTEXT.md` / `CONTEXT-MAP.md` for ubiquitous language;
this estate keeps that vocabulary in each repo's CLAUDE.md, so it points there.

Two things here are load-bearing, so resist tidying them:

`disable-model-invocation: true` is the whole design. Only the reader knows when they
stopped following, so the agent must never reach for this on its own. Upstream:
"The agent will not reach for it on its own, and it shouldn't."

The brevity is deliberate, not a stub. Telling a model to "be concise" makes it drop
context along with the words. Naming the *listener's* state instead gets fewer words and
the missing context restored at the same time. Every line added here dilutes that.
-->
