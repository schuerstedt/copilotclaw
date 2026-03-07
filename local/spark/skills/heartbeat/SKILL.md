# heartbeat — Spark liveness pings

Post a heartbeat comment to the designated GitHub issue to signal Spark is alive.
Crunch monitors this issue and alerts if no beat in 70+ minutes.

## Usage

```bash
# Post a heartbeat
SPARK_HEARTBEAT_ISSUE=90 bash local/spark/skills/heartbeat/run.sh

# Or via spark.py
python3 spark.py --heartbeat
```

## How it works

1. Spark posts a comment to issue #90 every 30 minutes (daemon mode)
2. Crunch's cloud heartbeat checks issue #90 on every run (~30m schedule)
3. If no beat in 70+ minutes → Crunch posts an alert to #11
4. Spark's `--monitor` command also checks heartbeat freshness locally

## Environment

| Var | Default | Notes |
|-----|---------|-------|
| `SPARK_HEARTBEAT_ISSUE` | `90` | GitHub issue number for liveness pings |
| `SPARK_HEARTBEAT_INTERVAL` | `30` | Minutes between beats in daemon mode |
| `SPARK_NODE` | hostname | Node identifier shown in beats |

## Keeping it alive

The heartbeat issue (#90) must never be closed — it's infrastructure.

In daemon mode (`spark.py --daemon`), heartbeats are posted automatically.
You can also run it from a cron job:

```bash
*/30 * * * * cd ~/spark && SPARK_HEARTBEAT_ISSUE=90 python3 spark.py --heartbeat >> logs/heartbeat.log 2>&1
```
