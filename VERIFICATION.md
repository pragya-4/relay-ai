# Verification evidence

## Current release · 25 November 2026

The [submission frontend](https://relay-ai-shashwat-tripathi.gauzyadage64.chatgpt.site) passed the complete desktop and mobile browser suite against the public Railway backend. The Vercel alias below is a separate deployment and is excluded from the submission links.

The production FastAPI service passed all **22** assertions in `scripts/verify_live.py` during this audit. During the first public browser check the Vercel page loaded, requested health from a misspelled Railway hostname, and displayed **Backend unavailable**. The initial preflight against the correct backend returned HTTP 400. After appending the Vercel origin and redeploying the existing Railway service, the same preflight passed.

| Requirement | Status | Evidence |
|---|---|---|
| GET /health, database readiness and configured pool | VERIFIED | Production returned HTTP 200, status ok, two keys and caching enabled. |
| POST /chat, metadata, real text and two working keys | VERIFIED | The live suite forced each key to answer independently. Live replies included model, source, integer latency, per-turn input/output usage, key ID and preceding failures. |
| Multi-turn state, isolation, system prompt and ordered history | VERIFIED | Production recalled a fresh marker, returned alternating user/assistant history and preserved existing history after failures. Contract tests separately cover session isolation and custom prompt persistence. |
| Built-in LiteLLM caching and identity | VERIFIED | The actual Cache is keyed by model and the full ordered message list, excluding session ID. Live replay returned identical text and tokens, null key ID and zero fallbacks. The integration suite exercises responses beyond the default four-message cache cutoff. |
| Automatic real-error handling and header hook | VERIFIED | Prior loopback tests returned HTTP 429, 500, 502 and 503 from the Gemini adapter’s upstream. Production hook tests exercised 429 and 500 with a real surviving provider. Wildcard exhaustion returned the specified 503 JSON and made no partial write. |
| Input errors, all-key error and unknown session | VERIFIED | FastAPI contract tests exercise malformed JSON, blank/oversized messages, invalid sessions and unknown history. Production script verified errors and preservation of prior history. |
| SQLite schema and Docker volume | VERIFIED | Startup creates the schema and index. GitHub Actions started both containers, verified both ports, recreated the backend and read the original volume-backed session. |
| Railway volume survival across a production restart | VERIFIED | Stored a unique production chat before Railway redeployment. Deployment b3c46dca replaced ea6398f5 and reported SUCCESS. Health returned 200 and the full session history and metadata compared equal after deployment. SQLite targets /data/app.db. |
| Multi-stage builds, root Compose file and make up/down | VERIFIED | The public Docker workflow ran successfully at commit 99c3f6e and stopped the stack cleanly. |
| Public submission frontend → Railway | VERIFIED | Fresh Chromium sent real requests to Railway from the submission URL. Live 930 ms, cache 1 ms, identical text and 47 input / 2 output tokens. Verified page reload, 429 and 500 failover, readable 503, retry, recall, all mandatory selectors and mobile submission with no uncaught page errors. |
| React controls, mandatory test IDs and reply metadata | VERIFIED | Four Chromium tests passed again with stubbed API responses. TypeScript and production build passed. A clean local frontend build targeting the correct public backend passed the expanded connected test at desktop and 390 px mobile width. |
| Public frontend availability | VERIFIED | Fresh unsigned browser rendered the Vercel page; send control visible at 390 px without horizontal overflow. |
| Alternate Vercel deployment | FAILED | Browser attempted /health on 4q042940 instead of 4a042940. Railway now accepts the correct Vercel origin. The frontend still requires a production rebuild with the correct hostname. |
| Credentials excluded from public source | VERIFIED | Scanned all 32 tracked blobs in the five-commit history at 99c3f6e for common credential signatures and private environment filenames. The reviewed package had previously been checked against both literal provider keys. This is a scoped check. |
| Public GitHub source and deployment URLs | VERIFIED | Repository, frontend HTML and backend health were reachable without login. |
| Public 2–3 minute video with candidate narration | BLOCKED | Requires the candidate’s recording and public video URL. See DEMO.md. |

## Measured requests

| Run | Live ms | Cache ms | Input/output tokens on both responses |
|---|---:|---:|---:|
| Candidate’s earlier local API check | 4059 | 1 | 31 / 14 |
| Candidate’s earlier Railway API check | 844 | 1 | 28 / 2 |
| Fresh Railway API check | 479 | 1 | 30 / 2 |
| Corrected local frontend → Railway, fresh Chromium | 596 | 1 | 47 / 2 |

Each row is one prompt pair. Server-measured milliseconds exclude network round-trip time. The connected browser check also verified 429/500 fallback, readable 503, successful recovery, multi-turn recall, reload creating a new session, metadata rendering, no uncaught JavaScript errors and successful mobile submission. That build ran on localhost with the production Railway origin.

## Test history and reproduction

The earlier backend run passed 32 FastAPI/SQLite contract cases and 4 parameterized LiteLLM integration cases. The loopback upstream used fixture content. Production generation above used real Gemini. The earlier 404 does not establish a definitive provider-side cause. A separate adapter failure was reproducible: the pinned Gemini adapter rejected the temperature override before HTTP. Relay removed that parameter, aligned model defaults and enabled caching for longer histories.

Run `python -m pytest backend/tests -q` after installing backend development dependencies. From frontend run `npm ci`, `npm run typecheck`, `npm run build`, `npx playwright install chromium` and `npm run test:e2e`. The public browser check can be reproduced in PowerShell:

```powershell
$env:EXPECTED_API_ORIGIN = 'https://relay-backend-production-4a042940.up.railway.app'
node tests/connected.mjs https://relay-ai-shashwat-tripathi.gauzyadage64.chatgpt.site
```

[Docker run](https://github.com/pragya-4/relay-ai/actions/runs/45505325376) · [Public app](https://relay-ai-shashwat-tripathi.gauzyadage64.chatgpt.site) · [Public health](https://relay-backend-production-4a042940.up.railway.app/health)
