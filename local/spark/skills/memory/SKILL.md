# memory — Cosmos DB persistent memory

Read and write memories to Azure Cosmos DB. Shared brain with Crunch.

## Usage

```bash
# Remember a fact
bash local/spark/skills/memory/run.sh remember "Spark runs on macserver with claude+gemini"

# Recall recent memories
bash local/spark/skills/memory/run.sh recall "macserver"

# Show last 5 memories
bash local/spark/skills/memory/run.sh recent
```

Or from spark.py:

```python
from spark import spark_remember, spark_recall

# Store a fact
spark_remember("Spark runs on macserver with claude+gemini", doc_type="memory")

# Recall
docs = spark_recall(query="macserver")
for d in docs:
    print(d["content"])
```

## Environment

| Var | Required | Default |
|-----|----------|---------|
| `COSMOS_ENDPOINT` | ✅ | — |
| `COSMOS_KEY` | ✅ | — |

## Memory types (partition keys)

| Type | Use for |
|------|---------|
| `memory` | General facts, preferences |
| `diary` | Session/event logs |
| `fact` | Permanent truths (rarely change) |
| `session` | Per-session scratch notes |
| `spark` | Spark-specific observations |

## Shared with Crunch

Both Spark and Crunch write to the same Cosmos DB:
- DB: `crunch`
- Container: `memories`
- Source field identifies writer: `spark/macserver` vs `heartbeat`

This means Spark can READ Crunch's diary entries and vice versa. Cross-agent memory!
