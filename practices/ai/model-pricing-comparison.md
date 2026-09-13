# Comparing Model Pricing Across Vendors

> How to get comparable per-token pricing for frontier and open-weight models,
> what the comparison is good for, and the three ways it misleads you.

## The problem

There is no neutral API that returns every vendor's prices. Each publishes its
own pricing page in its own units, on its own schedule, with promotional rates
that expire. Comparing them by hand is slow enough that nobody does it, so model
choices get made once and then never revisited — which is how a workload ends up
on a deprecated model at a price nobody has looked at in a year.

## Three routes, and when each is right

| Route | Covers | Good for | Fails at |
|---|---|---|---|
| **Aggregator API** (OpenRouter `/api/v1/models`) | 445 models, 59 vendors, incl. 155 open-weight | Screening, change detection, open-weight coverage | Partner surfaces (Vertex, Bedrock); is a list rate, not your bill |
| **Vendor pricing pages** | One vendor, authoritative | The number you actually commit to | Manual; no change detection; partner pages are separate from first-party |
| **Your own billing** | What you actually spent | Cost per *task*, the only number that decides anything | Retrospective; tells you nothing about a model you haven't run |

Use the aggregator to notice movement. Use the vendor page to confirm a number
before acting on it. Use your billing to decide whether the change is worth
making.

## The aggregator route

OpenRouter's model endpoint is public and unauthenticated. Prices are per token
as decimal strings, so multiply by 1e6 for the familiar $/1M figure.

```bash
curl -s https://openrouter.ai/api/v1/models | python3 -c "
import sys, json
for m in sorted(json.load(sys.stdin)['data'], key=lambda x: x['id']):
    p = m.get('pricing', {})
    i = float(p.get('prompt') or 0) * 1e6
    o = float(p.get('completion') or 0) * 1e6
    print(f\"{m['id']:<48} in \${i:>7.2f}  out \${o:>7.2f}  ctx {m.get('context_length')}\")
"
```

Useful properties:

- **Batch rates are separate rows** with a `:batch` suffix, usually half the
  standard rate. Worth folding into any comparison — batch is the single largest
  discount available on most vendors and it applies to any workload that
  tolerates async.
- **Open-weight models are covered**, which no first-party pricing page does:
  155 rows spanning llama, qwen, deepseek, mistral, gemma, nemotron and kimi,
  including 7 genuinely free-tier models. This is the only route that puts an
  open-weight option and a frontier model in the same units.
- **A `$0.00` price and an absent price are different things.** Zero means
  explicitly free; absent means no published rate. Treat them separately or a
  missing rate silently reads as free.

Spot-checked against first-party on 2026-09-13: Anthropic Opus 5 at $5/$25 and
Sonnet 5 at $2/$10 matched exactly. That is a sample of one vendor, not a
guarantee about the rest.

## Three ways this misleads you

**1. Partner surfaces are priced separately and are not in the feed.** Vertex AI
and Bedrock bill on their own sheets. If a workload runs on Vertex, the
aggregator cannot tell you what it costs — and code that falls back to Vertex
when an API key is absent is running on a price the feed never showed you.

**2. Sticker rate is not spend.** Thinking tokens, cache-read rates, and batch
discounts move the real number more than the headline does. A model at twice the
per-token rate that finishes the task in one pass instead of three is cheaper.
Judge cost per *completed task*, not per request.

**3. "Cheaper" in a marketing email is relative to something unstated.** A launch
announcement comparing a new model to its immediate predecessor says nothing
about the older, cheaper model you are actually running. Promotional rates also
expire — check the post-promo number, which is frequently several times the rate
you would be leaving.

Worked example, from the Gemini 2.5 deprecation in 2026-09: the launch email for
3.8 Flash led with a promotional $0.75/$3.75 as a cost *reduction*. Against
2.5 Flash at $0.30/$2.50, it was an increase — and at the stated post-promo
$1.50/$7.50, a 5x increase on input. Meanwhile the migration target Google
actually recommended, 3.1 Flash Lite at $0.25/$1.50, was cheaper than the model
being deprecated on both sides. The comparison took one curl; the email's framing
pointed the opposite direction.

## Making it standing

A pricing check nobody runs is worth nothing, and a check that runs silently is
worth about the same. `digest/model_pricing.py` in this repo runs inside the
Friday digest wrapper and:

- snapshots a **watchlist**, not the catalog — models we plausibly run. 445 rows
  of noise defeats the purpose
- diffs against the previous snapshot and files a GitHub issue only on a **>=5%**
  move or a model leaving the feed. Vendors reprice in cents; a 1% tripwire
  firing weekly trains you to ignore the issues
- writes `data/model_pricing.md`, committed weekly, so git history carries the
  diff even when nothing crosses the threshold
- says "baseline run, no comparison possible" on first run rather than "no
  material change" — a zero-result run and a genuinely quiet week must not
  produce the same output

Registered in [`AUTOMATION.md`](../../AUTOMATION.md) with a freshness tell and
kill criteria, like every other standing job.

## Where Used

- **best-practices** — `digest/model_pricing.py`, wired into
  `scripts/run_weekly_digest.sh`; report at `data/model_pricing.md`
- **crumbl-ops** — the Vertex Gemini 2.5 migration
  ([crumbl-ops#2572](https://github.com/michaeladickson/crumbl-ops/issues/2572))
  is the case this doc was written from; note that its traffic is on Vertex, so
  the feed screens options but cannot price its current bill

## Sources

- OpenRouter models endpoint: `https://openrouter.ai/api/v1/models`
- Anthropic pricing: the `claude-api` skill's model table (first-party rates)
- Google Cloud model lifecycle and Vertex pricing documentation
