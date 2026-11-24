# Relay AI interview preparation

## Architecture in one minute

The React client creates a fresh session ID on page load and sends only the current user message. FastAPI loads that session's system prompt and ordered SQLite history, then tries one LiteLLM Router alias per Gemini key, in order. LiteLLM performs the provider call. The application owns the bounded fallback loop. A local LiteLLM Cache is keyed by model and the full system-plus-conversation message list, so equivalent first turns can be reused across sessions. After inference succeeds, SQLite atomically stores the user and assistant pair with per-request token and latency metadata. Failures return a JSON error and write nothing.

## Design choices to explain

- Why the browser sends one message instead of the whole transcript: the backend remains the source of truth for context and prevents client history drift.
- Why use an alias per key? It makes selection deterministic and lets the gateway count exactly which keys failed.
- The alias that returned a valid completion supplies key_id.
- Why cache identity excludes session and key: identical prompts across new sessions should hit; key rotation should not change content identity.
- Why simulations bypass cache reads: otherwise a warmed answer could prevent a simulated failure from exercising failover.
- Why user and assistant rows share one transaction: provider failures cannot leave an orphan user message.
- Concurrency limitation: SQLite handles persistence; striped session locks and the local cache are process-local. Use one worker/replica for deterministic session ordering/cache behavior.
- Security limitation: public unauthenticated sessions and the failure-simulation hook are acceptable only for the evaluation demo. Use low-quota keys, no sensitive prompts, and turn off simulation afterward.

## Likely questions and concise answers

**How do you know a response is cached?**  The LiteLLM cache returns the stored response object for the exact model/messages parameters. Metadata is assigned only when that lookup succeeds; token usage comes from the stored provider response.

**What makes a cache entry unique?**  Model identifier and the full ordered messages sent to the model, including system prompt and conversation history. Session ID, API key, and unrelated HTTP metadata are not part of the identity.

**What happens if both keys fail?**  The application exhausts its ordered LiteLLM aliases; FastAPI returns `503 {"detail":"all providers unavailable"}` and performs no database writes.

**How is the simulation safe for concurrent requests?**  The header is parsed into request-local data and checked immediately before each call. The shared Router is never reconfigured. Simulated calls skip cache reads.

**What do atomic writes guarantee?**  Inference is completed before the database transaction. One transaction inserts exactly one user row and one assistant row under a per-session lock. Provider failures happen before either insert. A client retry after a lost response can create another turn because the API has no idempotency key.

**How are tokens counted?**  The assistant response's provider usage values describe that completion; the application does not sum prior turns. Cache hits retain the same usage object.

**What caused the inference failure?** The earlier 404 has no confirmed root cause. In this revision a reproducible local adapter failure occurred before HTTP because the configured model rejects the temperature override. The backend default also disagreed with the environment template. We corrected both and exercised the actual Gemini adapter with fixture responses. Both rotated keys subsequently generated real answers through the local FastAPI app. A fresh-session replay reported 0 ms after rounding versus 7746 ms live, with identical 29/7 token usage. Public backend acceptance remains outstanding.

**What evidence would convince you that failover works?** At the HTTP boundary, record a synthetic 429 for the first key and watch the next connection use the second key. Compare the reported alias and count. In production, use the request-local header to skip key one and require a substantive provider reply through key two. Check VERIFICATION.md for which step has run.
