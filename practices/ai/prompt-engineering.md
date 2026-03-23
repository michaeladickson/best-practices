# Prompt Engineering Patterns

## Classification Prompts

Structure for any classification task (email triage, transaction categorization, etc.):

```
You are a [role] for [context].

Classify the following [input type] into one of these categories:
- CATEGORY_A: description
- CATEGORY_B: description
- ...

Return JSON:
{
  "category": "one of the above",
  "confidence": 0.0-1.0,
  "summary": "1 sentence explanation"
}

Rules:
- [Disambiguation rules for edge cases]
- If uncertain, choose [default] with low confidence
```

### Key Principles
- Enumerate valid categories explicitly (never open-ended)
- Include disambiguation rules for edge cases
- Request confidence scores to support human review thresholds
- Truncate input to 3000 chars to control tokens

## Context-Aware Prompts

Inject domain knowledge to improve accuracy:

```python
# Spending categorizer — household context
prompt = f"""
The user lives in {location} with {family_details}.
Known merchants:
- "Otf Tenleytown" = Orangetheory Fitness
- "Wp Gtown" = Whole Foods Georgetown

Rules:
- Restaurant charges during a trip = TRIPS, not DINING
- Charges within 2 days at same destination = one trip
"""
```

## Structured Output Prompts

When you need specific JSON back:

1. Define the exact schema in the prompt
2. Provide an example if the schema is complex
3. Include validation rules ("relevance_score must be 1-10")
4. Add honesty instructions ("if nothing matches, return empty arrays")

## Conversational AI with Full Context

For advisor/chat features, load comprehensive context:

```typescript
// Health advisor — load 90 days of user data
const context = {
  recentFood: await fetchFoodLogs(userId, 90),
  workouts: await fetchWorkouts(userId, 90),
  sleep: await fetchSleep(userId, 90),
  metrics: await fetchMetrics(userId, 90),
  medicalRecords: await fetchMedicalRecords(userId),
};

const systemPrompt = buildAdvisorPrompt(context);
// Manage conversation history: user → 'user', assistant → 'model'
```

## Draft Generation

For generating responses/emails:

- Use higher temperature (0.7) for natural language
- Provide tier-specific instructions (enthusiastic vs. polite decline)
- Include template variables: `{store_name}`, `{from_name}`
- Set max tokens (2048) to keep responses focused
- Always have a static fallback string if AI fails

## Automated Code Review Prompts

For CI/CD integration (GitHub Actions):

```yaml
# Weekly review prompt
prompt: |
  Review the following files for:
  1. Security vulnerabilities (Critical/High/Medium/Low)
  2. Performance issues
  3. Code quality

  Output as GitHub issue body with checkboxes.
  Ignore: test files, migrations, generated code.
```

## Where Used

- **crumbl-ops**: Email classification (`src/cs/classifier.py`), draft generation (`src/cs/responder.py`)
- **wealth-mgmt**: Transaction categorization with household context (`src/spending/categorizer.py`)
- **healthpulse**: Food parsing, health advisor (Edge Functions)
