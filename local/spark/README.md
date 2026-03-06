# ⚡ Spark — Local AI Agent Runner

The minimal self-evolving local AI agent. Plant it on any machine. Watch it work.

## Concept

```
GitHub Issues ──┐
                ├──► spark.py ──► AI Agent ──► Post result back
Gitea Issues ───┘         │
                          └──► spark/update: rewrites itself
```

## Quick Start

```bash
# On any Linux/macOS/WSL machine:
bash local/spark/install.sh

# Authenticate with GitHub:
gh auth login

# Test run:
source ~/spark/.env && python3 ~/spark/spark.py

# Daemon mode:
python3 ~/spark/spark.py --daemon
```

## Trigger a task

1. Open any GitHub issue in `Copilotclaw/copilotclaw`
2. Add label `spark/ready`
3. Within 30s: Spark claims it, runs it, posts result

## Available agents (auto-detected, first wins)

| Agent | Install |
|-------|---------|
| `claude` | `npm i -g @anthropic-ai/claude-code` |
| `gemini` | `npm i -g @google/gemini-cli` |
| `codex` | `npm i -g @openai/codex` |
| `opencode` | `npm i -g opencode` |
| `qwen-code` | `npm i -g qwen-code` |
| `ollama` | `curl https://ollama.ai/install.sh \| sh` |

## Self-update

Create an issue with label `spark/update`. The body can be:
- A fenced ` ```python ` block with the full new spark.py
- Plain instructions — Spark will use the local AI to rewrite itself

## Gitea local runner

Copy `.gitea/workflows/spark.yml` to your Gitea repo. With `act_runner` connected,
Spark runs as a Gitea Actions job triggered by issue labels — no polling needed.

## Scale

Each machine runs its own Spark instance. They all watch the same issue queue.
First to claim an issue wins (`spark/claimed` label). 

Add a `SPARK_NODE` env var so results show which machine did the work.
