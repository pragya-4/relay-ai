# Relay AI demo recording script (2–3 minutes)

Record your own screen and voice only after live URLs are added and the acceptance checklist passes. Replace each bracketed value with a real, reachable URL. Do not show `.env`, API keys, or private prompts. No synthetic recording is included.

## 0:00–0:20 — Introduce the deployed app

Open https://relay-ai-shashwat-tripathi.gauzyadage64.chatgpt.site in a private browser window.

Say: “This is Relay AI, a React chat client backed by FastAPI, LiteLLM, and SQLite. The backend keeps the session history, and the client sends only each new message.”

## 0:20–0:50 — Live inference and cache

Pick a fresh run label such as the current time, then send `Run <label>: What is the capital of France?` and point out the live source, model, latency, and per-request token counts. Select **New conversation**, submit the exact same text, and show the identical reply marked `LLM_CACHE` with null provider key and matching token counts.

Say: “The cache key uses the model and complete message history, not the session ID, so the identical first turn can reuse a response across sessions.”

## 0:50–1:20 — Real key fallback through the test hook

Select **Key 1 · rate limit**, send a unique question, and show a real reply marked `key_2` with one fallback attempt. Repeat with **Key 1 · server error** and a fresh prompt.

Say: “The request-local header simulates one failed key; the gateway calls LiteLLM with the next key alias. The answer itself still comes from Gemini.”

## 1:20–1:40 — Exhaustion and recovery

Select **All keys unavailable**, send a fresh prompt, and show the readable 503 with no assistant answer. Select **Normal inference**, send a new prompt, and show recovery.

## 1:40–2:10 — API and persistence

Show `[PUBLIC_BACKEND_URL]/health`, then use PowerShell/Postman/curl to call `POST /chat` and `GET /sessions/{session_id}/messages`. Show the successful user/assistant pair in chronological order and assistant metadata. Do not put credentials in command history or the recording.

## 2:10–2:40 — Code and honest limits

Show the public repository, Dockerfiles, named `relay_data` volume, and `VERIFICATION.md`. Mention that SQLite history lives on the persistent volume and that the in-memory cache and session locks require one worker, and describe any remaining limitations accurately.

End by showing `[PUBLIC_FRONTEND_URL]` and `[PUBLIC_BACKEND_URL]` in the browser address bar. Upload the recording to a public link and check it in a signed-out/private window before submitting.
