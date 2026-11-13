"""NVIDIA NIM (OpenAI-compatible). Writes explanations."""
import os, requests
def ask_nvidia(system, user):
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Authorization": "Bearer " + os.environ["NVIDIA_API_KEY"]},
        json={"model": os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct"),
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
              "temperature": 0.2, "max_tokens": 500}, timeout=40)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
