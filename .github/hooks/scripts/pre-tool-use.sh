#!/bin/bash
# PreToolUse hook — fires before every tool call
#
# Responsibilities:
#   1. Quota guard: deny if premium usage >= 90%
#   2. Safety guard: block obviously destructive patterns
#   3. Audit log: append every tool call to memory.log
#
# Input JSON (on stdin): { timestamp, cwd, toolName, toolArgs }
# Output JSON (to stdout): { permissionDecision, permissionDecisionReason }
#   — only "deny" is currently acted upon; omitting output = allow

set -euo pipefail
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName // "unknown"' 2>/dev/null || echo "unknown")
TOOL_ARGS=$(echo "$INPUT" | jq -r '.toolArgs // ""' 2>/dev/null || echo "")
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
AUDIT_LOG="$REPO_ROOT/state/tool-audit.log"

# Audit log (non-blocking — failures here must not deny the tool)
echo "[${TS}] ${TOOL_NAME}" >> "$AUDIT_LOG" 2>/dev/null || true

# --- Safety guard: block known-destructive shell patterns ---
if [ "$TOOL_NAME" = "bash" ]; then
  COMMAND=$(echo "$TOOL_ARGS" | jq -r '.command // ""' 2>/dev/null || echo "")
  if echo "$COMMAND" | grep -qE 'rm -rf /[^t]|rm -rf /tmp/../|format [A-Z]:|DROP (TABLE|DATABASE)'; then
    jq -cn '{
      permissionDecision: "deny",
      permissionDecisionReason: "Blocked by safety guard: destructive command pattern detected"
    }'
    exit 0
  fi
fi

# --- Quota guard: check Copilot premium usage ---
# Only run quota check if BILLING_PAT is available (avoid slow fail)
if [ -n "${BILLING_PAT:-}" ]; then
  USAGE_OUT=$(bash "$REPO_ROOT/.github/skills/session-stats/scripts/premium-usage.sh" "copilotclaw" 2>/dev/null || echo "unavailable")

  # Extract numeric percentage
  PCT=$(echo "$USAGE_OUT" | grep -oP '\d+(?=%)' | head -1 || echo "0")

  if [ -n "$PCT" ] && [ "$PCT" -ge 90 ] 2>/dev/null; then
    jq -cn --arg usage "$USAGE_OUT" '{
      permissionDecision: "deny",
      permissionDecisionReason: ("Quota guard: Copilot premium at " + $usage + ". Pausing autonomous tool use. Ping Marcus to continue.")
    }'
    exit 0
  fi
fi

# Allow by default (no output also works but explicit is cleaner for debugging)
exit 0
