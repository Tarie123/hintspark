"""Google Gemini. Verifies explanations are grounded in the trace and don't leak the fix."""
import os, json, requests
def ask_gemini_json(prompt):
    m = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}, timeout=40)
    r.raise_for_status()
    return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
