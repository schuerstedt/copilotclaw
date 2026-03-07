#!/bin/bash
# PostToolUse hook — fires after every tool call completes
#
# Logs failures to memory.log for post-session review.
# Output is ignored by Copilot CLI.
#
# Input JSON (on stdin): { timestamp, cwd, toolName, toolArgs, toolResult }

set -euo pipefail
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName // "unknown"' 2>/dev/null || echo "unknown")
RESULT_TYPE=$(echo "$INPUT" | jq -r '.toolResult.resultType // "unknown"' 2>/dev/null || echo "unknown")
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

# Only log failures to memory.log (avoid noise from successful calls)
if [ "$RESULT_TYPE" = "failure" ] || [ "$RESULT_TYPE" = "denied" ]; then
  RESULT_TEXT=$(echo "$INPUT" | jq -r '.toolResult.textResultForLlm // ""' 2>/dev/null | head -c 200 || echo "")
  echo "[${TS}] HOOK:ToolFailure tool=${TOOL_NAME} result=${RESULT_TYPE} msg=${RESULT_TEXT}" >> "$REPO_ROOT/memory.log" 2>/dev/null || true
fi

exit 0
