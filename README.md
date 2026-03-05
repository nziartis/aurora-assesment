# Member Q&A

A minimal API service that answers natural-language questions about member data.

## Endpoint

```
POST /ask
Content-Type: application/json

{ "question": "When is Layla planning her trip to London?" }
```

Response:

```json
{ "answer": "Layla is planning her trip to London on..." }
```

## Running locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# edit .env and paste your key

# 3. Start the server
uvicorn main:app --reload
```

Get a free Google AI Studio API key at https://aistudio.google.com/apikey

## Example queries

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "When is Layla planning her trip to London?"}'

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many cars does Vikram Desai have?"}'

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are Amina'\''s favorite restaurants?"}'
```

## How it works

1. At startup, all member messages are fetched from the upstream API and cached in memory (auto-refreshed every 10 minutes)
2. Each incoming question is matched to a member by fuzzy name matching against known member names
3. That member's full message history is passed to Gemini 2.5 Flash alongside the question
4. The answer is returned as `{ "answer": "..." }`

## Approach

### Name-filtered context (chosen)

The service fetches all member messages from the upstream API at startup and caches them in memory. When a question arrives, the member's name is extracted from the question text using fuzzy matching against known member names. That member's full message history is then passed to Gemini 2.5 Flash alongside the question, and the model synthesizes an answer drawing on the complete chronological record.

### Full context dump

One alternative considered was to include every message from all members in each prompt. This avoids any filtering logic and guarantees no context is missed, but at roughly 3,350 messages it produces around 170,000 tokens per request, which is slow and exhausts free-tier rate limits quickly. It also sends every member's private history for every question, regardless of relevance.

### Retrieval-augmented generation

A RAG approach would embed each message as a vector, store them in a vector database, and retrieve only the most semantically relevant messages for each question. This scales to millions of messages and handles questions that do not mention a specific name. For this dataset, ten named members where every question identifies its subject, the added infrastructure and embedding pipeline would be disproportionate. It remains the natural next step if the member count grows significantly.

### Structured extraction

A third option was to parse all messages at startup and extract structured facts per member into a knowledge store, then query that store at request time. This would be very fast and require no per-request LLM calls, but it requires defining a schema for every fact type in advance and breaks for any question type not anticipated during extraction. Given that the questions are open-ended natural language, this approach is too brittle.

## Data Findings

| Finding | Detail |
|---|---|
| 10 members | 288–365 messages each over exactly 1 year |
| Truncated messages | 2 cut-off mid-sentence ("I want to", "I finally") |
| PII in plaintext | 2 credit cards, 24 phone numbers, 8 emails sent as plain text |
| Synthetic data signals | Uniform 5–7 day max gaps across all members, exactly 365-day span |
| Unreliable API | total field sometimes misreports; pagination breaks intermittently |

Run `python analyze.py` to reproduce these findings.
