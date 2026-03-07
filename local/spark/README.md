# ⚡ Spark — Local AI Agent Runner

The minimal self-evolving local AI agent. Plant it on any machine. Watch it work.

## Concept

```
GitHub Issues ──┐
                ├──► spark.py ──► AI Agent ──► Post result back
Gitea Issues ───┘         │
                          ├──► spark/update: rewrites itself
                          ├──► --monitor: checks Crunch + self
                          └──► --remember/--recall: Cosmos DB memory
```

## Quick Start

```bash
# On any Linux/macOS/WSL machine:
bash local/spark/install.sh

# Authenticate with GitHub:
gh auth login

# Test run:
source ~/spark/.env && python3 ~/spark/spark.py --detect

# Daemon mode (polls + heartbeat every 30m):
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

## Skills

Skills live in `~/spark/skills/<name>/`. Each has `SKILL.md` (docs) + `run.sh` (runner).

| Skill | Purpose |
|-------|---------|
| `azure` | Call Azure AI Foundry LLM (Grok, GPT, Claude) |
| `memory` | Read/write Cosmos DB shared brain |
| `heartbeat` | Post liveness ping to GitHub #90 |

## Memory (Cosmos DB)

Spark shares a persistent brain with Crunch:

```bash
python3 spark.py --remember "Spark runs on macserver with claude+gemini"
python3 spark.py --recall "macserver"
```

Requires `COSMOS_ENDPOINT` + `COSMOS_KEY` in `~/spark/.env`.

## Monitoring

```bash
python3 spark.py --monitor  # check Crunch CI + own heartbeat
```

Posts alert to #11 if something looks wrong.

## Self-update

Create an issue with label `spark/update`. The body can be:
- A fenced ` ```python ` block with the full new spark.py
- Plain instructions — Spark will use the local AI to rewrite itself

## Gitea local runner

Copy `.gitea/workflows/spark.yml` to your Gitea repo. With `act_runner` connected,
Spark runs as a Gitea Actions job triggered by issue labels — no polling needed.

The workflow includes:
- ✅ Single concurrency group (no more double posting)
- ✅ Heartbeat on every scheduled run
- ✅ COSMOS + AZURE env vars wired in

## Scale

Each machine runs its own Spark instance. They all watch the same issue queue.
First to claim wins (`spark/claimed`). Double-post guard is built in.
