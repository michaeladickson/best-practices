# Gemini Integration

## Client Setup

Always prefer `GEMINI_API_KEY` over Vertex AI to avoid gcloud reauth issues.

```python
def _get_gemini_client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return genai.Client(api_key=api_key)
    project = os.environ.get("GCP_PROJECT_ID", "")
    if not project:
        raise ValueError("Set GEMINI_API_KEY or GCP_PROJECT_ID")
    return genai.Client(vertexai=True, project=project, location="us-central1")
```

## Model Selection

- **gemini-3.8-flash**: Default for all tasks. AI Studio shuts `gemini-2.5-flash` down on 2026-12-01 and reroutes it to `gemini-3.5-flash-lite`; run on the same inputs, the lite model returned an empty digest at its default `minimal` thinking and rewrote untouched doc lines at `medium`, so the digest moved to 3.8 Flash instead (#78).
- **Run the old and new model on the same real input before a bump.** Google's named successor is a routing default, not a quality claim. The pin test's docstring (`tests/test_model_strings_pinned.py`) gives the steps.
- **Watch the retirement calendar of the surface you call.** AI Studio and Vertex AI date the same model differently: on 2026-11-09 Vertex listed `gemini-3.6-flash` for retirement on 2026-11-19 while AI Studio listed no date. AI Studio dates go on its deprecations page, Vertex dates on its model-versions page. The weekly run reads both and matches them against each repo's pinned ids (`digest/model_pricing.py`).
- **No sampling parameters on Gemini 3.x.** From 3.5 Flash-Lite and 3.6 Flash on, the API ignores `temperature`, `top_p` and `top_k` and says later models will reject them with a 400. Steer determinism with the system instruction or a response schema; set depth with `thinking_level`, not `thinking_budget`.

## Prompt Structure

1. **Role context**: "You are an email classifier for a Crumbl Cookies franchise"
2. **Valid outputs**: Enumerate categories/fields explicitly (not open-ended)
3. **Domain context**: Inject household/investor/business profile
4. **Concrete rules**: "charges at Disney = TRIPS not DINING"
5. **Output format**: Request JSON with exact schema
6. **Validation instruction**: "If nothing is relevant, return empty arrays"

## Structured Output Parsing

```python
text = response.text
# Strip markdown code fences
if "```json" in text:
    text = text.split("```json")[1].split("```")[0]
elif "```" in text:
    text = text.split("```")[1].split("```")[0]

try:
    return json.loads(text.strip())
except json.JSONDecodeError as e:
    log.error("json_parse_failed", error=str(e), response=text[:200])
    return None
```

Always handle markdown fence stripping — Gemini frequently wraps JSON in fences.

## Batch Processing for AI

```python
BATCH_SIZE = 50

# Separate cached vs uncached
uncached = [t for t in transactions if t.id not in cache]

for i in range(0, len(uncached), BATCH_SIZE):
    batch = uncached[i:i + BATCH_SIZE]
    results = call_gemini(batch)
    cache.update(results)
    save_cache()  # Persist after each batch
```

- Truncate input content to 3000-4000 chars to control token usage
- Cache results by ID to avoid re-processing
- Save cache after each batch (crash recovery)

## Error Handling

- Wrap all Gemini calls in try/except
- Log failures with `exc_info=True`
- Return sensible defaults (fallback classification, static template)
- Never raise on AI failure — always graceful degradation
- Rule-based fallback on Gemini failure (keyword matching for classification)

## Edge Functions (Mobile/Serverless)

For mobile apps, keep API keys server-side:

```typescript
// Supabase Edge Function (Deno)
const ai = new GoogleGenAI({ apiKey: Deno.env.get('GEMINI_API_KEY')! });

Deno.serve(async (req) => {
  const { userId, message } = await req.json();
  const response = await ai.models.generateContent({ ... });
  return new Response(JSON.stringify({ reply: response.text }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
});
```

App never touches GEMINI_API_KEY — Edge Function proxies all AI calls.

## Where Used

- **crumbl-ops**: Email classification, draft generation (`src/cs/`)
- **wealth-mgmt**: Transaction categorization, macro digest analysis
- **healthpulse**: Food parsing, health advisor, stretch recommendations (via Edge Functions)
- **best-practices**: RSS digest analysis
- **command-center**: Email-triage classification, daily-briefing comms digest, context-updater classification
