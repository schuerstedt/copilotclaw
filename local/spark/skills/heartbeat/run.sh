#!/usr/bin/env bash
# heartbeat/run.sh — Post Spark liveness heartbeat to GitHub
set -euo pipefail
export SPARK_HEARTBEAT_ISSUE="${SPARK_HEARTBEAT_ISSUE:-90}"
python3 "$(dirname "$0")/../../spark.py" --heartbeat
