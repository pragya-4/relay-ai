# Relay AI · 2 minute 40 second recording script

Open the [chat](https://relay-ai-shashwat-tripathi.gauzyadage64.chatgpt.site), [health endpoint](https://relay-backend-production-4a042940.up.railway.app/health) and [repository](https://github.com/pragya-4/relay-ai) in separate tabs. Open a PowerShell terminal. Hide dashboards, secrets, notifications and unrelated tabs. Use a new four-digit run label each time, including after a rehearsal. The candidate speaks the narration.

| Time | Action | Say |
|---|---|---|
| 0:00–0:15 | Show the public chat and health indicator. | “I’m Shashwat Tripathi. I built Relay AI to keep a conversation going when a provider key fails and to show exactly how each reply was produced.” |
| 0:15–0:40 | Send **Run 9286. Answer in one word: what color is an emerald?** Replace 9286 with your fresh label. Point at the reply metadata. | “This answer came from Gemini. Here are the model, responding key, server latency, and the tokens used for this turn.” Read the actual values. |
| 0:40–1:02 | Select **New conversation**. Paste the identical first prompt. | “This is a different session with the same model and complete prompt. LiteLLM returned the stored reply. The usage matches the first response. There’s no responding key on a cache hit.” Read the new latency. |
| 1:02–1:27 | Select **Key 1 · rate limit**. Send **Name one moon of Jupiter.** Show key_2 and one fallback. | “The selector sends the request-local X-Simulate-Failure header. The first key behaves as if it returned 429. Key two still makes a real inference request.” |
| 1:27–1:45 | Select **All keys unavailable**. Send **Remember this code: cedar-9286.** Show the error, then retry the restored input under normal inference. | “All keys failing produces a readable 503. The failed turn wasn’t stored. The next request can use the pool normally.” |
| 1:45–2:08 | Ask **Which exact code did I ask you to remember?** Switch to PowerShell and show the history request below. | “The client sent just the new message. FastAPI loaded the session’s earlier turns from SQLite. The history endpoint returns those turns in chronological order.” |
| 2:08–2:40 | Show health, then the repository’s Compose file and Docker workflow. | “Health checks the database and the configured key pool. SQLite is mounted at /data. I keep one worker because the locks and response cache are process-local. Successful message pairs are committed together so a failed provider call leaves history intact.” |

## Prepare PowerShell before recording

```powershell
$api = 'https://relay-backend-production-4a042940.up.railway.app'
$sid = 'video-' + [guid]::NewGuid().ToString()
$body = @{session_id=$sid; message='Name one moon of Jupiter.'} | ConvertTo-Json
Invoke-RestMethod "$api/health"
Invoke-RestMethod "$api/chat" -Method Post -Headers @{'X-Simulate-Failure'='key_1=500'} -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 5
Invoke-RestMethod "$api/sessions/$sid/messages" | ConvertTo-Json -Depth 6
```

This terminal example uses its own session. To show the UI session instead, copy its full session_id from the chat request in the browser’s Network panel and use it in the final command. Upload the narrated recording and open its link signed out before adding it to SUBMISSION.md.
