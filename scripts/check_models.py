"""List-model preflight for each configured Gemini key. Sends no generation request."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
keys = list(dict.fromkeys(key.strip() for key in os.getenv("LLM_API_KEYS", "").split(",")
                          if key.strip() and not key.strip().startswith("YOUR_")))
model = os.getenv("LLM_MODEL", "gemini/gemini-3.5-flash-lite").removeprefix("gemini/")
if len(keys) < 2:
    sys.exit("Two distinct configured keys required.")

success = True
for index, key in enumerate(keys, start=1):
    page = None
    available = False
    try:
        while True:
            params = {"pageSize": 100}
            if page:
                params["pageToken"] = page
            url = "https://generativelanguage.googleapis.com/v1beta/models?" + urlencode(params)
            with urlopen(Request(url, headers={"x-goog-api-key": key}), timeout=20) as response:
                data = json.load(response)
            available = any(item["name"] == "models/" + model and
                            "generateContent" in item.get("supportedGenerationMethods", [])
                            for item in data.get("models", []))
            page = data.get("nextPageToken")
            if available or not page:
                break
        print(f"key_{index}: {model} generation listed = {available}")
        success = success and available
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"key_{index}: catalog request failed ({getattr(exc, 'code', type(exc).__name__)})")
        success = False
sys.exit(0 if success else 1)
