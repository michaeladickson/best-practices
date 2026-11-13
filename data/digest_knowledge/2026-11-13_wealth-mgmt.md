# Digest: wealth-mgmt — 2026-11-13

## Top Posts

- **Gemini Decisions API** (Simon Willison) — relevance 9/10
  Google released the Gemini Decision 1 API, a specialized non-generative model designed for closed-set choices, yes/no checks, and rubric scoring. It returns calibrated probabilities and choices with 150-250ms end-to-end latency at $0.10 per million input tokens with free output tokens.
  Why: wealth-mgmt uses Gemini for transaction categorization, which can be migrated to this faster, non-generative decision model to eliminate JSON parsing issues and obtain confidence scores.

- **Google built an AI model that can’t write a sentence — and that’s the point** (The New Stack) — relevance 8/10
  Covers the mechanics of Gemini Decision 1, which evaluates up to 1,000 independent closed-choice questions across a 256k context window in a single pass without token-by-token text generation.
  Why: The API's ability to evaluate multiple items in a single pass makes high-throughput financial transaction classification significantly cheaper and more deterministic.

- **Producer prices surge at 6.5% annual pace as Fed officials signal hike** (CFO Dive) — relevance 7/10
  Producer prices increased at a 6.5% annual rate, prompting Federal Reserve officials to signal potential interest rate hikes to counteract persistent wholesale inflation pressures.
  Why: Provides immediate real-world economic context for the platform's FRED macro analysis pipeline to assess rate hike risk on asset allocation and factor exposure.

- **parse_number() as a SQLite extension: C vs Rust** (Simon Willison) — relevance 6/10
  Benchmarks building a SQLite custom extension function to strip currency symbols ('$', '£', commas, '%') and parse numbers directly in SQL, comparing Rust and C implementations.
  Why: wealth-mgmt uses SQLite locally and frequently parses financial amounts, percentages, and balances from varied CSVs, Plaid payloads, and web scrapes.

- **Progressive disclosure** (Matt Pocock (AI Hero)) — relevance 5/10
  Explains the pattern of loading only minimal context pointers into prompts while keeping full instructions and domain standards encapsulated until specifically invoked by the task.
  Why: Directly applies to structuring wealth-mgmt's complex prompts for investor profiles, tax account rules (Roth vs traditional), and macro thesis generation.

## Recommendations

- [SMALL] Adopt Gemini Decision API for Transaction Categorization
  Replace generative Gemini chat prompts for lifestyle transaction categorization with the new Gemini Decision 1 API. Provide the defined taxonomy of lifestyle categories as choice criteria and receive deterministic category assignments and probability scores in under 250ms without output token costs.
  Inspired by: Gemini Decisions API (Simon Willison) and Google built an AI model that can't write a sentence (The New Stack)
  Impact: Eliminates JSON syntax parsing failures, drops categorization inference latency by ~70%, reduces API spend, and exposes confidence scores to flag ambiguous transactions for user review.
  Where it fits: FastAPI backend transaction ingestion service (replacing the current Gemini batch categorization routine).
  First step: Write a standalone Python test script calling the Gemini Decision 1 endpoint with a sample batch of 20 unformatted Plaid transaction descriptions against the existing lifestyle category list.
  Risks: Gemini Decision 1 requires a strict closed set of labels; adding dynamic user-defined categories requires passing updated candidate lists in the request schema.

- [MEDIUM] Build PPI-Driven Rate Shock Regime Detector in FRED Pipeline
  Implement an automated macro trend detection rule that evaluates producer price index trends (FRED series PPIACO/WPUFD49207) against the effective federal funds rate and 10-year Treasury yields. When wholesale inflation accelerates past threshold rates, automatically trigger an 'Inflationary Pressure / Rate Shock' regime tag.
  Inspired by: Producer prices surge at 6.5% annual pace as Fed officials signal hike (CFO Dive)
  Impact: Enriches macro digest summaries with concrete inflation momentum indicators and automatically steers generated investment theses to evaluate duration risk and software multiple compression.
  Where it fits: Macro economic analysis module alongside existing FRED data fetchers.
  First step: Add the PPI core/headline series IDs to the FRED ingestion script and calculate a trailing 3-month annualized rate of change.
  Risks: Economic indicators are frequently revised by the BLS/FRED retroactively, which could shift regime classification labels on older dates.

- [SMALL] Implement SQLite parse_number Function for Financial Strings
  Add a custom SQLite scalar function (`parse_number`) in the local database connection setup (via `sqlite3.create_function` in Python or a compiled extension) that strips commas, currency symbols, and percentages, converting strings to clean floats directly during SQL queries.
  Inspired by: parse_number() as a SQLite extension: C vs Rust (Simon Willison)
  Impact: Simplifies SQL queries and aggregations across raw manual asset entries, transaction strings, and dividend tables without needing intermediate Python sanitization loops.
  Where it fits: Database connection factory / initialization module in the FastAPI backend.
  First step: Register a fast regex-free `parse_number` helper via `connection.create_function('parse_number', 1, ...)` in the SQLite database setup and test it against sample transaction strings.
  Risks: Python-registered SQLite functions are slightly slower than compiled C extensions on multi-million row datasets, though for personal wealth datasets the difference will be negligible.
