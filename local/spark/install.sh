#!/bin/bash
# ⚡ Spark Install Script
# Works on: Ubuntu/Debian, Arch, macOS, Raspberry Pi, VPS, WSL
# Usage: bash install.sh [--no-service]

set -euo pipefail

SPARK_HOME="${SPARK_HOME:-$HOME/spark}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NO_SERVICE="${1:-}"

echo "⚡ Spark installer"
echo "   Home: $SPARK_HOME"
echo ""

# ── 1. Python ────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "📦 Installing Python..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python
    elif command -v brew &>/dev/null; then
        brew install python3
    fi
fi
python3 --version

# ── 2. gh CLI ────────────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
    echo "📦 Installing gh CLI..."
    if command -v apt-get &>/dev/null; then
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
            | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
            | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt-get update -qq && sudo apt-get install -y -qq gh
    elif command -v brew &>/dev/null; then
        brew install gh
    else
        echo "⚠️  Install gh manually: https://cli.github.com"
    fi
fi

# ── 3. Spark home ────────────────────────────────────────────────────────────
mkdir -p "$SPARK_HOME/logs"

# Copy files
cp "$SCRIPT_DIR/spark.py"  "$SPARK_HOME/spark.py"
cp "$SCRIPT_DIR/SPARK.md"  "$SPARK_HOME/SPARK.md"
chmod +x "$SPARK_HOME/spark.py"

# ── 4. .env ───────────────────────────────────────────────────────────────────
ENV_FILE="$SPARK_HOME/.env"
if [ ! -f "$ENV_FILE" ]; then
    NODE_NAME="${SPARK_NODE:-$(hostname)}"
    cat > "$ENV_FILE" << ENVEOF
# ⚡ Spark Configuration
# Edit and then: source ~/spark/.env && python3 ~/spark/spark.py --daemon

export SPARK_REPO="Copilotclaw/copilotclaw"
export SPARK_NODE="${NODE_NAME}"
export SPARK_LABELS="spark/ready,dispatch/local"
export SPARK_CLAIMED_LABEL="spark/claimed"
export SPARK_POLL_INTERVAL="30"
export SPARK_LOG="$HOME/spark/logs/spark.log"
export SPARK_IDENTITY_FILE="$HOME/spark/SPARK.md"

# Optional: Gitea local issues
# export GITEA_URL="http://localhost:3000"
# export GITEA_TOKEN="your-token-here"
# export GITEA_REPO="owner/repo"

# Optional: GitHub PAT (if gh auth login not set)
# export GH_TOKEN="ghp_..."
ENVEOF
    echo "📝 Created $ENV_FILE — edit it then source it"
else
    echo "📝 $ENV_FILE already exists (not overwritten)"
fi

# ── 5. Detect available agents ────────────────────────────────────────────────
echo ""
echo "🤖 Agent detection:"
for agent in claude gemini codex opencode qwen-code ollama; do
    if command -v "$agent" &>/dev/null; then
        echo "   ✅ $agent"
    else
        echo "   ❌ $agent (not installed)"
    fi
done

# ── 6. Systemd service ────────────────────────────────────────────────────────
if [ "$NO_SERVICE" != "--no-service" ] && command -v systemctl &>/dev/null; then
    SERVICE_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"

    cat > "$SERVICE_DIR/spark.service" << SVCEOF
[Unit]
Description=Spark ⚡ Local AI Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$SPARK_HOME
EnvironmentFile=$SPARK_HOME/.env
ExecStart=/usr/bin/python3 $SPARK_HOME/spark.py --daemon
Restart=on-failure
RestartSec=30
StandardOutput=append:$SPARK_HOME/logs/spark.log
StandardError=append:$SPARK_HOME/logs/spark.log

[Install]
WantedBy=default.target
SVCEOF

    echo ""
    echo "🔧 systemd service written: $SERVICE_DIR/spark.service"
fi

# ── 7. Cron alternative ───────────────────────────────────────────────────────
cat > "$SPARK_HOME/cron-entry.sh" << 'CRONEOF'
#!/bin/bash
# Add to crontab: */1 * * * * bash ~/spark/cron-entry.sh
source "$HOME/spark/.env"
python3 "$HOME/spark/spark.py" >> "$HOME/spark/logs/spark.log" 2>&1
CRONEOF
chmod +x "$SPARK_HOME/cron-entry.sh"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━ ⚡ Spark installed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Authenticate gh CLI (if not already):"
echo "   gh auth login"
echo ""
echo "2. Edit config:"
echo "   nano $SPARK_HOME/.env"
echo ""
echo "3. Run once (test):"
echo "   source $SPARK_HOME/.env && python3 $SPARK_HOME/spark.py"
echo ""
echo "4a. Run as daemon:"
echo "   source $SPARK_HOME/.env && python3 $SPARK_HOME/spark.py --daemon"
echo ""
echo "4b. Or systemd (if available):"
echo "   systemctl --user enable spark && systemctl --user start spark"
echo ""
echo "4c. Or cron (every minute):"
echo "   crontab -e   →   add: */1 * * * * bash $SPARK_HOME/cron-entry.sh"
echo ""
echo "5. Trigger a task:"
echo "   Go to $SPARK_REPO issues → open any issue → add label 'spark/ready'"
echo "   Spark picks it up in <30s!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
