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

- **gemini-2.5-flash**: Default for all tasks. Fast, cheap, good enough for classification, summarization, structured output.
- **Temperature**: `0.1` for classification/structured output, `0.7` for creative drafting.

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
