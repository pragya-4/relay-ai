# Verification evidence

25 November 2026. The uploaded React and FastAPI application was used as the baseline.

| Area | Observed result |
|---|---|
| Backend contract | 32 pytest cases passed against FastAPI and temporary SQLite databases using the existing gateway double. Includes validation, ordered history, rollback on error, isolation, simulation switch, and persistence across app restarts. |
| Gateway integration | 4 parameterized cases passed with LiteLLM 1.110.0, its actual local cache and Gemini adapter. A loopback HTTP server returned 429, 500, 502 and 503 for the first credential. Each case observed the second credential at the provider boundary. Repeating a request across sessions produced identical text and usage without another provider call, including a six-message context. Both-provider exhaustion returned 503 and left no session. The upstream supplied fixture text. |
| Frontend | npm clean install, TypeScript check and Vite production build passed. Four Playwright tests passed in headless Chromium with stubbed API replies. They checked input clearing, nested metadata, error recovery, new session after reload and one-shot headers. |
| Public UI | Public deployment succeeded. A fresh browser opened the chat UI and observed “Backend unavailable”. |
| Docker | Compose v2.39.4 validated the rendered configuration using placeholder configuration. Make targets resolved. This runner denied access to the Docker daemon socket, so the revised images and restart with the named volume remain unverified. |
| Live inference | PASS against Google from local FastAPI. The owner confirmed the two rotated projects had billing disabled. Both catalogs listed the configured model. Both keys separately generated replies. The measured live/cache pair was 7746 ms / 0 ms (rounded), with identical text and 29 input / 7 output tokens. |
| Live API and connected browser | PASS on localhost with Google. The API acceptance script verified simulated 429/500, all-key 503, independent key generation, unchanged history after errors, multi-turn recall, metadata and SQLite history. Chromium exercised the production React build over real HTTP and confirmed reload, cache metadata, lower latency, failover and readable 503. |
| Public backend and production acceptance | Open. Public backend provisioning and acceptance are pending. |
| Voice demo | Script available. Recording and public video URL pending. |

The local integration exposed a provider error the old tests missed. The pinned LiteLLM Gemini adapter rejects a temperature override for the configured model before sending HTTP. Removing that parameter allowed requests through the adapter. It also defaults to skipping cache operations above four messages. Relay explicitly allows longer histories.

Run the suite with Python 3.12 and the pinned backend dependencies. A runner configured with SOCKS proxies also needs httpx's optional socks dependency. In a clean checkout use `python -m pytest backend/tests -q`. For the frontend use `npm ci`, `npm run typecheck`, `npm run build`, `npx playwright install chromium`, then `npm run test:e2e` from `frontend/`. An installed Chrome/Chromium executable can be selected with `CHROME_PATH`.

For production run the catalog preflight and the live acceptance script described in the README, then exercise the connected public UI and confirm database persistence after a backend restart. Sign out before checking submission links.
