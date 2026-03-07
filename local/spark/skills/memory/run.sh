#!/usr/bin/env bash
# memory/run.sh — Cosmos DB memory operations for Spark
# Usage:
#   bash run.sh remember "Your fact here" [type]
#   bash run.sh recall "search term"
#   bash run.sh recent [limit]
set -euo pipefail

CMD="${1:?Usage: $0 <remember|recall|recent> [args]}"

ENDPOINT="${COSMOS_ENDPOINT:?COSMOS_ENDPOINT not set}"
KEY="${COSMOS_KEY:?COSMOS_KEY not set}"
NODE="${SPARK_NODE:-$(hostname)}"

case "$CMD" in
  remember)
    CONTENT="${2:?Usage: $0 remember 'fact'}"
    TYPE="${3:-memory}"
    python3 "$(dirname "$0")/../../spark.py" --remember "$CONTENT" --memory-type "$TYPE"
    ;;
  recall)
    QUERY="${2:-}"
    python3 "$(dirname "$0")/../../spark.py" --recall "$QUERY"
    ;;
  recent)
    python3 "$(dirname "$0")/../../spark.py" --recall ""
    ;;
  *)
    echo "Unknown command: $CMD. Use: remember | recall | recent" >&2
    exit 1
    ;;
esac
