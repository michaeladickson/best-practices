# Model pricing watch

Source: OpenRouter `/api/v1/models` list rates, fetched 2026-09-13 21:03 UTC.

**These are list rates on OpenRouter's platform, not a bill.** Vertex AI
and Bedrock price separately and are not represented here — crumbl-ops'
Gemini traffic runs on Vertex, so this table cannot answer what it costs.
Thinking tokens, cache-read rates, and batch discounts move real spend
more than the headline rate does. Use this to notice movement; confirm on
the vendor's own pricing page before acting.

Regenerated weekly by `digest/model_pricing.py`.

## Anthropic

| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |
|---|---|---|---|---|---|
| `anthropic/claude-opus-5` | $5.00 | $25.00 | $2.50 | $12.50 | 1,000,000 |
| `anthropic/claude-sonnet-5` | $2.00 | $10.00 | $1.00 | $5.00 | 1,000,000 |
| `anthropic/claude-haiku-4.5` | $1.00 | $5.00 | $0.50 | $2.50 | 200,000 |

## Google (in use)

| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |
|---|---|---|---|---|---|
| `google/gemini-2.5-flash` | $0.30 | $2.50 | $0.15 | $1.25 | 1,048,576 |
| `google/gemini-2.5-pro` | $1.25 | $10.00 | $0.62 | $5.00 | 1,048,576 |

## Google (migration targets)

| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |
|---|---|---|---|---|---|
| `google/gemini-3.1-flash-lite` | $0.25 | $1.50 | $0.12 | $0.75 | 1,048,576 |
| `google/gemini-3.5-flash-lite` | $0.30 | $2.50 | $0.15 | $1.25 | 1,048,576 |
| `google/gemini-3.5-flash` | $1.50 | $9.00 | $0.75 | $4.50 | 1,048,576 |
| `google/gemini-3.8-flash` | $0.75 | $3.75 | $0.38 | $1.88 | 1,048,576 |

## OpenAI

| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |
|---|---|---|---|---|---|
| `openai/gpt-5.4` | $2.50 | $15.00 | $1.25 | $7.50 | 1,050,000 |
| `openai/gpt-5.4-mini` | $0.75 | $4.50 | $0.38 | $2.25 | 400,000 |

## Open weight

| Model | Input $/1M | Output $/1M | Batch in | Batch out | Context |
|---|---|---|---|---|---|
| `qwen/qwen3.8-max-0902` | $2.00 | $6.00 | n/a | n/a | 1,000,000 |
| `deepseek/deepseek-v3.2` | $0.27 | $0.40 | n/a | n/a | 163,840 |
| `moonshotai/kimi-k3` | $2.65 | $13.28 | $3.00 | $15.00 | 1,048,576 |
| `google/gemma-4-31b-it` | $0.09 | $0.34 | $0.39 | $0.97 | 262,144 |
