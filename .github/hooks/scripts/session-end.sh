#!/bin/bash
# SessionEnd hook — fires when the Crunch session terminates
#
# Logs session end reason to memory.log.
# Output is ignored by Copilot CLI.
#
# Input JSON (on stdin): { timestamp, cwd, reason }

set -euo pipefail
INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // "unknown"' 2>/dev/null || echo "unknown")
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

echo "[${TS}] HOOK:SessionEnd reason=${REASON}" >> "$REPO_ROOT/memory.log" 2>/dev/null || true

exit 0
