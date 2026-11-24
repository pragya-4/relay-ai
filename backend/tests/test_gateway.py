"""Exercise the real LiteLLM router, Gemini adapter and local cache over loopback."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def gateway_api(tmp_path, monkeypatch):
    calls = []
    statuses = {}
    keys = ["fixture-first", "fixture-second"]

    class GeminiFixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            key = self.headers.get("x-goog-api-key") or parse_qs(urlsplit(self.path).query)["key"][0]
            calls.append((key, request))
            status = statuses.get(key, 200)
            if status != 200:
                result = {"error": {"code": status, "message": "fixture provider error",
                                    "status": "RESOURCE_EXHAUSTED" if status == 429 else "INTERNAL"}}
            else:
                result = {
                    "candidates": [{"content": {"role": "model", "parts": [{"text": "Fixture reply."}]},
                                    "finishReason": "STOP", "index": 0}],
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 3,
                                      "totalTokenCount": 15},
                }
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(("127.0.0.1", 0), GeminiFixture) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setenv("GEMINI_API_BASE", f"http://127.0.0.1:{server.server_port}")
            monkeypatch.setenv("LLM_API_KEYS", ",".join(keys))
            monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")
            monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
            monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
            monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
            with TestClient(create_app(db_path=str(tmp_path / "test.db"))) as client:
                yield client, calls, statuses
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_upstream_failure_cache_and_exhaustion(gateway_api, status):
    client, calls, statuses = gateway_api
    statuses["fixture-first"] = status

    def post(session, message="Hello", **kwargs):
        return client.post("/chat", json={"session_id": session, "message": message}, **kwargs)

    first = post("first")
    assert first.status_code == 200, first.text
    live = first.json()
    assert [c[0] for c in calls] == ["fixture-first", "fixture-second"]
    assert (live["metadata"]["key_id"], live["metadata"]["fallback_attempts"]) == ("key_2", 1)
    assert live["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    hit = post("second").json()
    assert hit["reply"] == live["reply"]
    assert hit["metadata"]["resolution_source"] == "LLM_CACHE"
    assert (hit["metadata"]["key_id"], hit["metadata"]["fallback_attempts"]) == (None, 0)
    for response in [live, hit]:
        assert (response["metadata"]["input_tokens"], response["metadata"]["output_tokens"]) == (12, 3)
    assert len(calls) == 2
    assert post("first", "Another turn").json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert [turn["role"] for turn in calls[-1][1]["contents"]] == ["user", "model", "user"]
    assert post("second", "Another turn").json()["metadata"]["resolution_source"] == "LLM_CACHE"
    assert post("first", "Third turn").json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    count = len(calls)
    assert post("second", "Third turn").json()["metadata"]["resolution_source"] == "LLM_CACHE"
    assert len(calls) == count
    assert post("simulated", headers={"X-Simulate-Failure": "key_1=429"}).json()["metadata"]["key_id"] == "key_2"
    statuses["fixture-second"] = 500
    failed = post("failed", "Both fail")
    assert failed.status_code == 503 and failed.json() == {"detail": "all providers unavailable"}
    assert client.get("/sessions/failed/messages").status_code == 404
