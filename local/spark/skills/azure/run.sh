#!/usr/bin/env bash
# azure/run.sh — Call Azure AI Foundry for LLM tasks
# Usage: bash run.sh "Your prompt here"
set -euo pipefail

PROMPT="${1:?Usage: $0 'your prompt'}"
MODEL="${AZURE_MODEL:-grok-4-1-fast-non-reasoning}"
ENDPOINT="${AZURE_ENDPOINT:?AZURE_ENDPOINT not set}"
APIKEY="${AZURE_APIKEY:?AZURE_APIKEY not set}"

python3 - <<PYEOF
import json, urllib.request, sys

prompt = """${PROMPT}"""
model  = "${MODEL}"
url    = "${ENDPOINT}/chat/completions?api-version=2024-05-01-preview"
body   = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 2000,
}).encode()

req = urllib.request.Request(url, data=body, method="POST", headers={
    "Content-Type": "application/json",
    "api-key": "${APIKEY}",
})
with urllib.request.urlopen(req, timeout=60) as r:
    data = json.load(r)
print(data["choices"][0]["message"]["content"].strip())
PYEOF
