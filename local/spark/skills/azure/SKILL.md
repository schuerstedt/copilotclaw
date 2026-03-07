# azure — Azure AI Foundry LLM

Call Azure AI Foundry for LLM tasks: summarisation, analysis, generation, reasoning.

## Usage

```bash
bash local/spark/skills/azure/run.sh "Your prompt here"
# or with model override:
AZURE_MODEL=grok-4-1-fast-non-reasoning bash local/spark/skills/azure/run.sh "prompt"
```

Or from spark.py:

```python
from spark import azure_llm
result = azure_llm("Summarise this issue: ...")
```

## Environment

| Var | Required | Default |
|-----|----------|---------|
| `AZURE_ENDPOINT` | ✅ | — |
| `AZURE_APIKEY` | ✅ | — |
| `AZURE_MODEL` | no | `grok-4-1-fast-non-reasoning` |

## Models available (AI Foundry)

- `grok-4-1-fast-non-reasoning` — default, fast, cheap. 50 RPM / 50k TPM
- `gpt-4.1` — free tier, good for general tasks
- `claude-sonnet-4.5` — premium, best reasoning

## Notes

- Use this instead of spawning sub-agents for summarisation/analysis
- Cost-effective: Grok model is fast and cheap
- Falls back gracefully with a clear message if not configured
