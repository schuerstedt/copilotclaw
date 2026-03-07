#!/usr/bin/env python3
"""
Spark ⚡ — Local AI Agent Runner

Polls GitHub Issues and/or local Gitea issues.
Auto-detects available AI agents and runs tasks.
Posts results back. Can update itself.

Usage:
  python3 spark.py                  # run once (cron/CI mode)
  python3 spark.py --daemon         # run forever (poll loop)
  python3 spark.py --issue 42       # process a specific issue
  python3 spark.py --heartbeat      # post liveness heartbeat
  python3 spark.py --detect         # detect available agents
  python3 spark.py --monitor        # check health of Crunch + self
  python3 spark.py --remember "fact" [--type memory]  # store to Cosmos DB
  python3 spark.py --recall "query"                   # search Cosmos DB

Environment:
  SPARK_REPO          GitHub repo  (default: Copilotclaw/copilotclaw)
  SPARK_NODE          Node name    (default: hostname)
  SPARK_LABELS        Comma-sep labels to watch (default: spark/ready,dispatch/local)
  SPARK_CLAIMED_LABEL Label to mark claimed (default: spark/claimed)
  SPARK_POLL_INTERVAL Seconds between polls (default: 30)
  SPARK_IDENTITY_FILE Path to SPARK.md injected as context (default: ./SPARK.md)
  SPARK_LOG           Log file path (default: ~/spark/spark.log)
  GITEA_URL           Gitea base URL (default: http://localhost:3000)
  GITEA_TOKEN         Gitea API token
  GITEA_REPO          Gitea repo owner/name (default: same as SPARK_REPO)
  GH_TOKEN            GitHub PAT for gh CLI (optional — gh auth login works too)
  COSMOS_ENDPOINT     Azure Cosmos DB endpoint for memory
  COSMOS_KEY          Azure Cosmos DB master key
  AZURE_ENDPOINT      Azure AI Foundry base URL (for skills)
  AZURE_APIKEY        Azure AI Foundry API key (for skills)
  CRUNCH_MONITOR_ISSUE  GitHub issue # to post alerts to (default: 11)
"""

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

NODE = os.getenv("SPARK_NODE", "").strip() or socket.gethostname()  # empty string fallback → hostname
REPO = os.getenv("SPARK_REPO", "Copilotclaw/copilotclaw")
WATCH_LABELS = [l.strip() for l in os.getenv("SPARK_LABELS", "spark/ready,dispatch/local").split(",")]
CLAIMED_LABEL = os.getenv("SPARK_CLAIMED_LABEL", "spark/claimed")
POLL_INTERVAL = int(os.getenv("SPARK_POLL_INTERVAL", "30"))
LOG_FILE = os.getenv("SPARK_LOG", str(Path.home() / "spark" / "spark.log"))
IDENTITY_FILE = os.getenv("SPARK_IDENTITY_FILE", str(Path(__file__).parent / "SPARK.md"))

GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000").rstrip("/")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_REPO = os.getenv("GITEA_REPO", REPO)

# Cosmos DB memory
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "").rstrip("/")
COSMOS_KEY = os.getenv("COSMOS_KEY", "")
COSMOS_DB = "crunch"
COSMOS_CONTAINER = "memories"

# Azure AI Foundry (for skills)
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "")
AZURE_APIKEY = os.getenv("AZURE_APIKEY", "")

# Monitoring
MONITOR_ISSUE = int(os.getenv("CRUNCH_MONITOR_ISSUE", "11"))

# Agent priority order — first one found wins
AGENT_PRIORITY = ["claude", "gemini", "codex", "opencode", "qwen-code"]

# ─── Logging ──────────────────────────────────────────────────────────────────

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("spark")


# ─── Identity ─────────────────────────────────────────────────────────────────

def load_identity() -> str:
    p = Path(IDENTITY_FILE)
    if p.exists():
        return p.read_text()
    return "You are Spark ⚡, a local AI agent. Do the task and be concise."


# ─── Agent detection ──────────────────────────────────────────────────────────

def detect_agent() -> str | None:
    """Return the first available agent CLI name, or None."""
    for agent in AGENT_PRIORITY:
        if shutil.which(agent):
            log.info(f"🤖 Agent detected: {agent}")
            return agent

    # Fallback: check ollama with a usable model
    if shutil.which("ollama"):
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = [l for l in result.stdout.strip().splitlines()[1:] if l.strip()]
                if lines:
                    model = lines[0].split()[0]
                    log.info(f"🤖 Ollama detected, best model: {model}")
                    return f"ollama:{model}"
        except Exception:
            pass

    return None


# ─── Run task ─────────────────────────────────────────────────────────────────

def build_prompt(identity: str, title: str, body: str, comments: list[dict]) -> str:
    comment_block = ""
    if comments:
        parts = [f"**{c.get('author', {}).get('login', '?')}**: {c.get('body', '')}" for c in comments]
        comment_block = "\n\nThread:\n" + "\n\n".join(parts)

    return f"""{identity}

---

## Task: {title}

{body or '(no description)'}
{comment_block}

---

Provide a thorough, useful response. If the task involves code, write it.
If analysis, provide it. Be concise but complete."""


def run_agent(agent: str, prompt: str, timeout: int = 300) -> tuple[str, str]:
    """
    Execute prompt with the given agent.
    Returns (output_text, status) where status is 'done' | 'error' | 'timeout'.
    """
    try:
        if agent.startswith("ollama:"):
            model = agent.split(":", 1)[1]
            cmd = ["ollama", "run", model, prompt]
        elif agent == "claude":
            cmd = ["claude", "--print", prompt]
        elif agent == "gemini":
            cmd = ["gemini", "-p", prompt]
        elif agent == "codex":
            cmd = ["codex", "--full-auto", prompt]
        elif agent == "opencode":
            cmd = ["opencode", "run", "-p", prompt]
        elif agent == "qwen-code":
            cmd = ["qwen-code", "--print", prompt]
        else:
            return f"Unknown agent: {agent}", "error"

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            output = result.stdout.strip() or result.stderr.strip()
            return output or "(no output)", "done"
        else:
            return f"Exit {result.returncode}: {result.stderr[:500]}", "error"

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s", "timeout"
    except Exception as e:
        return f"Execution error: {e}", "error"


def execute_task(issue: dict) -> tuple[str, str]:
    """Run the task in the issue. Returns (result_text, status)."""
    agent = detect_agent()
    if not agent:
        return (
            "⚠️ No AI agent available on this node.\n\n"
            "Install one: `npm install -g @anthropic-ai/claude-code` (Claude Code)\n"
            "or `npm install -g @google/gemini-cli` (Gemini CLI)\n"
            "or `curl https://ollama.ai/install.sh | sh && ollama pull llama3`",
            "no_agent",
        )

    identity = load_identity()
    title = issue.get("title", "Untitled")
    body = issue.get("body", "") or ""
    comments = issue.get("comments", [])

    prompt = build_prompt(identity, title, body, comments)
    log.info(f"⚙️  Running with {agent} (task: {title[:60]})")
    return run_agent(agent, prompt)


# ─── Self-update ──────────────────────────────────────────────────────────────

def apply_self_update(issue: dict) -> tuple[str, str]:
    """
    Apply a self-update from an issue labeled spark/update.
    The issue body should contain a code block with the new spark.py content,
    OR a diff, OR instructions for an AI to rewrite specific parts.
    """
    body = issue.get("body", "") or ""
    title = issue.get("title", "")

    spark_py = Path(__file__)
    backup = spark_py.with_suffix(".py.bak")

    # If body contains a fenced ```python block, use it directly
    code_match = re.search(r"```python\n(.*?)```", body, re.DOTALL)
    if code_match:
        new_code = code_match.group(1)
        backup.write_text(spark_py.read_text())
        spark_py.write_text(new_code)
        log.info(f"✅ Self-update applied from fenced code block")
        return f"✅ Applied code update from issue #{issue['number']}. Backup saved to {backup.name}.", "done"

    # Otherwise: let the AI figure it out
    agent = detect_agent()
    if not agent:
        return "⚠️ No agent available to apply self-update", "error"

    current_code = spark_py.read_text()
    prompt = f"""You are updating your own code (spark.py). Here is the current code:

```python
{current_code}
```

Here is the update request:
{title}

{body}

Output ONLY the complete updated Python file content. No explanations. No markdown fences.
Start with: #!/usr/bin/env python3"""

    new_code, status = run_agent(agent, prompt, timeout=120)
    if status == "done" and new_code.strip().startswith("#!"):
        backup.write_text(current_code)
        spark_py.write_text(new_code)
        log.info("✅ Self-update applied via AI")
        return f"✅ Applied AI-generated self-update for issue #{issue['number']}. Backup: {backup.name}", "done"
    else:
        return f"⚠️ Self-update failed: {new_code[:200]}", "error"


# ─── GitHub source ────────────────────────────────────────────────────────────

def gh_run(*args, check=True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(["gh"] + list(args), capture_output=True, text=True, check=check, env=env)


def github_fetch_tasks() -> list[dict]:
    """Fetch open issues matching any watch label that aren't yet claimed."""
    issues = {}
    for label in WATCH_LABELS:
        try:
            r = gh_run(
                "issue", "list",
                "--repo", REPO,
                "--label", label,
                "--state", "open",
                "--json", "number,title,body,labels,comments",
                "--limit", "20",
            )
            for issue in json.loads(r.stdout):
                issues[issue["number"]] = issue
        except Exception as e:
            log.warning(f"GitHub fetch failed for label '{label}': {e}")

    unclaimed = []
    for issue in issues.values():
        label_names = {l["name"] for l in issue.get("labels", [])}
        if CLAIMED_LABEL not in label_names:
            unclaimed.append(issue)
    return unclaimed


def github_comment(number: int, body: str):
    gh_run("issue", "comment", str(number), "--repo", REPO, "--body", body)


def github_add_label(number: int, label: str):
    gh_run("issue", "edit", str(number), "--repo", REPO, "--add-label", label)


def github_remove_label(number: int, label: str):
    gh_run("issue", "edit", str(number), "--repo", REPO, "--remove-label", label, check=False)


def ensure_github_label(name: str, color: str = "0075ca", description: str = ""):
    """Create the label if it doesn't exist."""
    gh_run(
        "label", "create", name,
        "--repo", REPO,
        "--color", color,
        "--description", description,
        "--force",
        check=False,
    )


def ensure_gitea_labels():
    """Create standard Spark labels in the local Gitea repo if they don't exist."""
    if not GITEA_TOKEN:
        return
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    existing = gitea_api("GET", f"/repos/{owner}/{repo}/labels?limit=50") or []
    existing_names = {l["name"] for l in existing}
    wanted = [
        ("spark/ready",      "fbca04", "Spark: task ready for local agent"),
        ("spark/claimed",    "0075ca", "Spark: task claimed by a node"),
        ("spark/update",     "e4e669", "Spark: self-update instruction"),
        ("dispatch/local",   "d4c5f9", "Dispatch to local (Spark) agent"),
        ("dispatch/github",  "c2e0c6", "Bridged from GitHub — reply goes back there too"),
    ]
    for label_name, color, desc in wanted:
        if label_name not in existing_names:
            gitea_api("POST", f"/repos/{owner}/{repo}/labels", {
                "name": label_name,
                "color": f"#{color}",
                "description": desc,
            })


# ─── Gitea source ─────────────────────────────────────────────────────────────

def gitea_api(method: str, path: str, data: dict | None = None) -> dict | list | None:
    """Make a Gitea API call."""
    if not GITEA_TOKEN:
        return None
    import urllib.request
    import urllib.error

    url = f"{GITEA_URL}/api/v1{path}"
    headers = {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.warning(f"Gitea API {method} {path}: {e.code} {e.reason}")
        return None
    except Exception as e:
        log.warning(f"Gitea API error: {e}")
        return None


def gitea_fetch_tasks() -> list[dict]:
    """Fetch open Gitea issues with watch labels that aren't claimed.
    Also picks up dispatch/github bridge issues missed by webhook."""
    if not GITEA_TOKEN:
        return []

    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    issues_raw = gitea_api("GET", f"/repos/{owner}/{repo}/issues?state=open&type=issues&limit=50")
    if not issues_raw:
        return []

    watch_set = set(WATCH_LABELS) | {"dispatch/github"}
    tasks = []
    for issue in issues_raw:
        label_names = {l["name"] for l in issue.get("labels", [])}
        if label_names & watch_set and CLAIMED_LABEL not in label_names:
            tasks.append({
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body", ""),
                "labels": issue.get("labels", []),
                "comments": [],
                "_source": "gitea",
            })
    return tasks


def gitea_fetch_issue(number: int) -> dict | None:
    """Fetch a single Gitea issue by number, including its comments."""
    if not GITEA_TOKEN:
        return None
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    issue = gitea_api("GET", f"/repos/{owner}/{repo}/issues/{number}")
    if not issue or issue.get("pull_request"):
        return None
    comments_raw = gitea_api("GET", f"/repos/{owner}/{repo}/issues/{number}/comments?limit=50") or []
    return {
        "number": issue["number"],
        "title": issue["title"],
        "body": issue.get("body", ""),
        "labels": issue.get("labels", []),
        "comments": [
            {"author": {"login": c.get("user", {}).get("login", "?")}, "body": c.get("body", "")}
            for c in comments_raw
        ],
        "_source": "gitea",
    }


def gitea_comment(number: int, body: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    gitea_api("POST", f"/repos/{owner}/{repo}/issues/{number}/comments", {"body": body})


def gitea_add_label(number: int, label_name: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    labels = gitea_api("GET", f"/repos/{owner}/{repo}/labels?limit=50") or []
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if label_id:
        gitea_api("POST", f"/repos/{owner}/{repo}/issues/{number}/labels", {"labels": [label_id]})


def gitea_remove_label(number: int, label_name: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    labels = gitea_api("GET", f"/repos/{owner}/{repo}/labels?limit=50") or []
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if label_id:
        gitea_api("DELETE", f"/repos/{owner}/{repo}/issues/{number}/labels/{label_id}")


# ─── GitHub → Gitea bridge ────────────────────────────────────────────────────

def extract_github_issue_number(body: str) -> int | None:
    """Extract a GitHub issue number embedded in a Gitea issue body."""
    m = re.search(r"<!-- GitHub: #(\d+) -->", body or "")
    return int(m.group(1)) if m else None


def bridge_github_to_gitea():
    """
    Poll GitHub for issues labelled 'dispatch/local' and mirror them into local Gitea
    as 'dispatch/github' issues.  The opened event will then trigger spark.py to
    process them; results get cross-posted back to the GitHub issue.
    """
    if not GITEA_TOKEN:
        return

    owner, repo_name = (GITEA_REPO + "/").split("/")[:2]

    # Find GitHub issue numbers already mirrored locally
    existing = gitea_api(
        "GET", f"/repos/{owner}/{repo_name}/issues?state=open&type=issues&limit=50"
    ) or []
    mirrored = {extract_github_issue_number(i.get("body", "")) for i in existing} - {None}

    try:
        r = gh_run(
            "issue", "list",
            "--repo", REPO,
            "--label", "dispatch/local",
            "--state", "open",
            "--json", "number,title,body,labels",
            "--limit", "20",
        )
        gh_issues = json.loads(r.stdout)
    except Exception as e:
        log.warning(f"Bridge: GitHub fetch failed: {e}")
        return

    # Get the dispatch/github label id once
    labels_list = gitea_api("GET", f"/repos/{owner}/{repo_name}/labels?limit=50") or []
    dg_label_id = next((l["id"] for l in labels_list if l["name"] == "dispatch/github"), None)

    for gh_issue in gh_issues:
        gh_num = gh_issue["number"]
        if gh_num in mirrored:
            continue

        title = f"[GitHub #{gh_num}] {gh_issue['title']}"
        body = (
            f"{gh_issue.get('body', '') or ''}\n\n"
            f"---\n"
            f"*Bridged from [Copilotclaw/copilotclaw#{gh_num}]"
            f"(https://github.com/{REPO}/issues/{gh_num})*\n"
            f"<!-- GitHub: #{gh_num} -->"
        )

        new_issue = gitea_api(
            "POST", f"/repos/{owner}/{repo_name}/issues",
            {"title": title, "body": body, "labels": [dg_label_id] if dg_label_id else []},
        )
        if new_issue:
            log.info(f"🌉 Bridged GitHub #{gh_num} → Gitea #{new_issue['number']}: {gh_issue['title'][:50]}")


# ─── Unified processing ───────────────────────────────────────────────────────

def claim(issue: dict) -> bool:
    """
    Claim an issue. Returns True if this node successfully claimed it,
    False if another process already claimed it (double-post guard).
    """
    source = issue.get("_source", "github")
    number = issue["number"]

    if source == "gitea":
        gitea_add_label(number, CLAIMED_LABEL)
        gitea_comment(number, f"⚡ **Spark claimed** (node: `{NODE}`). Working...")
        return True
    else:
        github_add_label(number, CLAIMED_LABEL)
        # Re-fetch the issue briefly after to detect a race: if the label was
        # already present before we added it, another node beat us to it.
        time.sleep(1)
        try:
            r = gh_run(
                "issue", "view", str(number), "--repo", REPO,
                "--json", "labels,comments",
            )
            fresh = json.loads(r.stdout)
            # Count how many "Spark claimed" comments already exist
            existing_claims = [
                c for c in fresh.get("comments", [])
                if "Spark claimed" in c.get("body", "")
            ]
            if existing_claims:
                log.warning(f"⚠️  #{number} already has a claim comment — another node beat us, skipping")
                return False
        except Exception:
            pass  # If re-fetch fails, proceed cautiously
        try:
            github_comment(number, f"⚡ **Spark claimed** (node: `{NODE}`). Working...")
        except Exception:
            pass
        return True


def post_result(issue: dict, result: str, status: str):
    source = issue.get("_source", "github")
    number = issue["number"]
    emoji = "✅" if status == "done" else "⚠️"
    agent = detect_agent() or "unknown"
    body = (
        f"{emoji} **Spark result** (node: `{NODE}`, agent: `{agent}`, status: `{status}`):\n\n"
        f"{result}\n\n"
        f"---\n*⚡ Spark local agent — {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*"
    )[:65000]

    if source == "gitea":
        gitea_comment(number, body)

        # Cross-post back to GitHub if this is a bridged issue
        label_names = {l["name"] for l in issue.get("labels", [])}
        if "dispatch/github" in label_names:
            gh_num = extract_github_issue_number(issue.get("body", ""))
            if gh_num:
                try:
                    github_comment(
                        gh_num,
                        f"⚡ **Spark (local) response** via node `{NODE}`:\n\n{result}"
                    )
                    log.info(f"↩️  Cross-posted result to GitHub #{gh_num}")
                except Exception as e:
                    log.warning(f"Failed to cross-post to GitHub #{gh_num}: {e}")

        # Remove the watch label if present (doesn't matter if none found)
        for label in WATCH_LABELS:
            if label in label_names:
                gitea_remove_label(number, label)
    else:
        try:
            github_comment(number, body)
        except Exception as e:
            log.error(f"Failed to post result to GitHub #{number}: {e}")
        for label in WATCH_LABELS:
            github_remove_label(number, label)


def process_issue(issue: dict):
    number = issue["number"]
    title = issue["title"]
    label_names = {l["name"] for l in issue.get("labels", [])}
    source = issue.get("_source", "github")

    # Guard: skip if already claimed (handles race between schedule + issue-labeled triggers)
    if CLAIMED_LABEL in label_names:
        log.info(f"⏭️  #{number} already claimed — skipping")
        return

    log.info(f"⚡ [{source}] #{number}: {title[:70]}")

    claimed = claim(issue)
    if not claimed:
        log.info(f"⏭️  #{number} claim lost to another node — skipping")
        return

    # Self-update special case
    if "spark/update" in label_names:
        result, status = apply_self_update(issue)
    else:
        result, status = execute_task(issue)

    post_result(issue, result, status)
    log.info(f"   ✅ #{number} done (status={status})")


def process_all():
    """One poll cycle — bridge GitHub→Gitea, then fetch from all sources and process."""
    tasks = []

    # Bridge: mirror GitHub dispatch/local issues into local Gitea
    try:
        bridge_github_to_gitea()
    except Exception as e:
        log.warning(f"Bridge error: {e}")

    # GitHub — fetch any unclaimed issues with watch labels
    try:
        gh_tasks = github_fetch_tasks()
        tasks.extend(gh_tasks)
        if gh_tasks:
            log.info(f"📋 GitHub: {len(gh_tasks)} task(s)")
    except Exception as e:
        log.warning(f"GitHub fetch error: {e}")

    # Gitea — fetch any unclaimed labeled issues (fallback for missed webhooks)
    try:
        gitea_tasks = gitea_fetch_tasks()
        tasks.extend(gitea_tasks)
        if gitea_tasks:
            log.info(f"📋 Gitea: {len(gitea_tasks)} task(s)")
    except Exception as e:
        log.warning(f"Gitea fetch error: {e}")

    for issue in tasks:
        try:
            process_issue(issue)
        except Exception as e:
            log.error(f"Error processing #{issue.get('number')}: {e}", exc_info=True)

    return len(tasks)


# ─── Entry point ──────────────────────────────────────────────────────────────

def check_gh_auth() -> bool:
    r = gh_run("auth", "status", check=False)
    if r.returncode != 0:
        log.warning("⚠️  gh CLI not authenticated. Run: gh auth login")
        return False
    return True


# ─── Heartbeat ────────────────────────────────────────────────────────────────

def post_heartbeat():
    """Post a liveness heartbeat comment to the designated GitHub issue."""
    issue_num = os.getenv("SPARK_HEARTBEAT_ISSUE", "")
    if not issue_num:
        log.info("SPARK_HEARTBEAT_ISSUE not set — skipping heartbeat")
        return

    agent = detect_agent()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        f"⚡ **Spark alive** | node: `{NODE}` | agent: `{agent or 'none'}` | `{ts}`"
    )
    try:
        github_comment(int(issue_num), body)
        log.info(f"💓 Heartbeat posted to #{issue_num}")
    except Exception as e:
        log.error(f"Heartbeat failed: {e}")


# ─── Cosmos DB Memory ─────────────────────────────────────────────────────────

def _cosmos_auth(verb: str, resource_type: str, resource_link: str, date: str) -> str:
    import hashlib, hmac, base64, urllib.parse
    text = f"{verb.lower()}\n{resource_type.lower()}\n{resource_link}\n{date.lower()}\n\n"
    key_bytes = base64.b64decode(COSMOS_KEY)
    sig = base64.b64encode(
        hmac.new(key_bytes, text.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    return urllib.parse.quote(f"type=master&ver=1.0&sig={sig}")


def _cosmos_request(method: str, path: str, body=None, resource_type: str = "",
                    resource_link: str = "", partition_key: str = None):
    import urllib.request, urllib.error, urllib.parse
    from email.utils import formatdate
    date = formatdate(usegmt=True)
    auth = _cosmos_auth(method, resource_type, resource_link, date)
    url = f"{COSMOS_ENDPOINT}{path}"
    headers = {
        "Authorization": auth,
        "x-ms-date": date,
        "x-ms-version": "2018-12-31",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if partition_key is not None:
        headers["x-ms-documentdb-partitionkey"] = json.dumps([partition_key])
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise RuntimeError(f"Cosmos {e.code}: {err[:200]}") from e


def spark_remember(content: str, doc_type: str = "memory", tags: list = None) -> str:
    """
    Write a memory to Cosmos DB.
    Returns the document ID on success, or error message.
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        log.warning("⚠️  COSMOS_ENDPOINT / COSMOS_KEY not set — memory not persisted")
        return "no-cosmos"
    import uuid
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    doc_id = f"spark-{doc_type}-{ts}-{uuid.uuid4().hex[:6]}"
    doc = {
        "id": doc_id,
        "type": doc_type,
        "content": content,
        "tags": tags or [],
        "source": f"spark/{NODE}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    coll_link = f"dbs/{COSMOS_DB}/colls/{COSMOS_CONTAINER}"
    try:
        _cosmos_request(
            "POST", f"/{coll_link}/docs",
            body=doc, resource_type="docs",
            resource_link=coll_link, partition_key=doc_type,
        )
        log.info(f"🧠 Memory written: {doc_id}")
        return doc_id
    except Exception as e:
        log.error(f"Memory write failed: {e}")
        return f"error: {e}"


def spark_recall(query: str = "", doc_type: str = None, limit: int = 5) -> list[dict]:
    """
    Recall recent memories from Cosmos DB.
    Returns list of matching documents.
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        return []
    import urllib.request, urllib.error
    coll_link = f"dbs/{COSMOS_DB}/colls/{COSMOS_CONTAINER}"
    if doc_type:
        sql = f"SELECT TOP {limit} * FROM c WHERE c.type='{doc_type}' ORDER BY c._ts DESC"
    elif query:
        safe_q = query.replace("'", "''")
        sql = f"SELECT TOP {limit} * FROM c WHERE CONTAINS(c.content, '{safe_q}') ORDER BY c._ts DESC"
    else:
        sql = f"SELECT TOP {limit} * FROM c ORDER BY c._ts DESC"

    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    auth = _cosmos_auth("POST", "docs", coll_link, date_str)
    url = f"{COSMOS_ENDPOINT}/{coll_link}/docs"
    headers = {
        "Authorization": auth,
        "x-ms-date": date_str,
        "x-ms-version": "2018-12-31",
        "Content-Type": "application/query+json",
        "Accept": "application/json",
        "x-ms-documentdb-isquery": "true",
        "x-ms-max-item-count": str(limit),
        "x-ms-documentdb-query-enablecrosspartition": "true",
    }
    data = json.dumps({"query": sql, "parameters": []}).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("Documents", [])
    except Exception as e:
        log.error(f"Memory recall failed: {e}")
        return []


# ─── Azure AI Foundry (skills LLM) ───────────────────────────────────────────

def azure_llm(prompt: str, model: str = "grok-4-1-fast-non-reasoning", max_tokens: int = 2000) -> str:
    """
    Call Azure AI Foundry for LLM tasks (summarisation, analysis, generation).
    Falls back gracefully if not configured.
    """
    if not AZURE_ENDPOINT or not AZURE_APIKEY:
        return "(Azure AI not configured — set AZURE_ENDPOINT and AZURE_APIKEY)"
    import urllib.request, urllib.error
    url = f"{AZURE_ENDPOINT}/chat/completions?api-version=2024-05-01-preview"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_APIKEY,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Azure LLM failed: {e}")
        return f"(Azure LLM error: {e})"


# ─── Monitoring ───────────────────────────────────────────────────────────────

def run_monitor() -> str:
    """
    Check health of Crunch (CI runs) and Spark (own heartbeat freshness).
    Returns a status report string. Posts alert to MONITOR_ISSUE if something is wrong.
    """
    issues = []
    report_lines = [f"⚡ **Spark monitor** | node: `{NODE}` | {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"]
    report_lines.append("")

    # 1. Check Crunch's last CI run
    try:
        r = gh_run(
            "run", "list", "--repo", REPO,
            "--limit", "3",
            "--json", "status,conclusion,startedAt,name,databaseId",
        )
        runs = json.loads(r.stdout)
        report_lines.append("**Crunch CI (last 3 runs):**")
        for run in runs:
            status = run.get("conclusion") or run.get("status", "?")
            icon = "✅" if status == "success" else ("⚠️" if status == "failure" else "🔄")
            started = run.get("startedAt", "?")[:16]
            report_lines.append(f"  {icon} `{run.get('name', '?')}` — {status} @ {started}")
            if status == "failure":
                issues.append(f"Crunch CI failure: {run.get('name')}")
    except Exception as e:
        report_lines.append(f"  ⚠️ Could not check CI: {e}")
        issues.append(f"CI check failed: {e}")

    report_lines.append("")

    # 2. Check own heartbeat freshness (issue #90 last comment)
    hb_issue = int(os.getenv("SPARK_HEARTBEAT_ISSUE", "90"))
    try:
        r = gh_run(
            "issue", "view", str(hb_issue), "--repo", REPO,
            "--json", "comments",
        )
        data = json.loads(r.stdout)
        comments = data.get("comments", [])
        # Find last spark heartbeat comment
        hb_comments = [c for c in comments if "Spark alive" in c.get("body", "")]
        if hb_comments:
            last_hb = hb_comments[-1]
            last_ts = last_hb.get("createdAt", "")
            if last_ts:
                from datetime import timedelta
                try:
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    age_min = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
                    if age_min > 70:
                        issues.append(f"Spark heartbeat stale: {age_min:.0f}m ago")
                        report_lines.append(f"**Heartbeat:** ⚠️ last beat {age_min:.0f}m ago (threshold 70m)")
                    else:
                        report_lines.append(f"**Heartbeat:** ✅ {age_min:.0f}m ago")
                except Exception:
                    report_lines.append(f"**Heartbeat:** last @ {last_ts}")
            else:
                report_lines.append("**Heartbeat:** last comment found but no timestamp")
        else:
            report_lines.append(f"**Heartbeat:** ⚠️ No heartbeat comments on #{hb_issue} yet")
            issues.append(f"No heartbeat on #{hb_issue}")
    except Exception as e:
        report_lines.append(f"**Heartbeat:** ⚠️ check failed: {e}")
        issues.append(f"Heartbeat check failed: {e}")

    report_lines.append("")

    # 3. Agent availability
    agent = detect_agent()
    report_lines.append(f"**Local agent:** {agent or '❌ none detected'}")

    report = "\n".join(report_lines)

    # Post alert if issues found
    if issues:
        alert = "🚨 **Spark monitor alert**\n\n" + "\n".join(f"- {i}" for i in issues)
        alert += f"\n\nNode: `{NODE}` | {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        try:
            github_comment(MONITOR_ISSUE, alert)
            log.warning(f"🚨 Monitor alert posted to #{MONITOR_ISSUE}: {issues}")
        except Exception as e:
            log.error(f"Failed to post monitor alert: {e}")
    else:
        log.info("✅ Monitor: all systems healthy")

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Spark ⚡ local AI agent runner")
    parser.add_argument("--daemon", action="store_true", help="Run as poll daemon")
    parser.add_argument("--issue", type=int, help="Process a specific GitHub issue number")
    parser.add_argument("--gitea-issue", type=int, dest="gitea_issue",
                        help="Process a specific Gitea issue number (triggered by issue label event)")
    parser.add_argument("--detect", action="store_true", help="Detect available agents and exit")
    parser.add_argument("--heartbeat", action="store_true", help="Post liveness heartbeat to SPARK_HEARTBEAT_ISSUE")
    parser.add_argument("--monitor", action="store_true", help="Check health of Crunch CI + own heartbeat, post alert if unhealthy")
    parser.add_argument("--remember", metavar="FACT", help="Store a fact in Cosmos DB memory")
    parser.add_argument("--recall", metavar="QUERY", help="Recall recent memories from Cosmos DB")
    parser.add_argument("--memory-type", default="memory", help="Memory type/partition for --remember (default: memory)")
    args = parser.parse_args()

    log.info(f"⚡ Spark starting | node={NODE} | repo={REPO}")

    if args.detect:
        agent = detect_agent()
        print(f"Agent: {agent or 'none found'}")
        print(f"Watched labels: {WATCH_LABELS}")
        print(f"Gitea: {'configured' if GITEA_TOKEN else 'not configured'}")
        print(f"Memory: {'configured' if COSMOS_ENDPOINT and COSMOS_KEY else 'not configured'}")
        print(f"Azure AI: {'configured' if AZURE_ENDPOINT and AZURE_APIKEY else 'not configured'}")
        return

    if args.heartbeat:
        check_gh_auth()
        post_heartbeat()
        return

    if args.monitor:
        check_gh_auth()
        report = run_monitor()
        print(report)
        return

    if args.remember:
        doc_id = spark_remember(args.remember, doc_type=args.memory_type)
        print(f"✅ Stored memory: {doc_id}")
        return

    if args.recall:
        docs = spark_recall(query=args.recall)
        if not docs:
            print("No memories found")
        for d in docs:
            ts = d.get("created_at", "?")[:19]
            print(f"[{ts}] ({d.get('type', '?')}) {str(d.get('content', ''))[:200]}")
        return

    # Bootstrap labels (best-effort — failures are non-fatal)
    try:
        ensure_github_label("spark/ready", "fbca04", "Spark: task ready for local agent")
        ensure_github_label("spark/claimed", "0075ca", "Spark: task claimed by a node")
        ensure_github_label("spark/update", "e4e669", "Spark: self-update instruction")
    except Exception:
        pass
    try:
        ensure_gitea_labels()
    except Exception:
        pass

    if args.gitea_issue:
        # Direct Gitea issue trigger (from issues: opened / labeled workflow event).
        # Process ANY unclaimed issue — no label required. Labels are only used to
        # decide whether to cross-post back to GitHub (dispatch/github) or self-update.
        if not GITEA_TOKEN:
            log.error("GITEA_TOKEN is required for --gitea-issue mode")
            sys.exit(1)
        issue = gitea_fetch_issue(args.gitea_issue)
        if not issue:
            log.error(f"Gitea issue #{args.gitea_issue} not found or is a PR")
            sys.exit(1)
        label_names = {l["name"] for l in issue.get("labels", [])}
        if CLAIMED_LABEL in label_names:
            log.info(f"Gitea issue #{args.gitea_issue} already claimed — skipping")
            return
        process_issue(issue)
        return

    if args.issue:
        # Single GitHub issue mode
        try:
            r = gh_run(
                "issue", "view", str(args.issue),
                "--repo", REPO,
                "--json", "number,title,body,labels,comments",
            )
            issue = json.loads(r.stdout)
            label_names = {l["name"] for l in issue.get("labels", [])}
            if not (label_names & set(WATCH_LABELS)):
                log.info(f"Issue #{args.issue} has no watched labels — skipping")
                return
            if CLAIMED_LABEL in label_names:
                log.info(f"Issue #{args.issue} already claimed — skipping (double-post guard)")
                return
            process_issue(issue)
        except Exception as e:
            log.error(f"Failed to process issue #{args.issue}: {e}", exc_info=True)
        return

    if args.daemon:
        log.info(f"🔄 Daemon mode | poll={POLL_INTERVAL}s")
        check_gh_auth()
        while True:
            try:
                n = process_all()
                if n == 0:
                    log.debug("No tasks found")
            except KeyboardInterrupt:
                log.info("Shutting down ⚡")
                break
            except Exception as e:
                log.error(f"Poll error: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL)
    else:
        # One-shot mode (cron / CI)
        check_gh_auth()
        n = process_all()
        log.info(f"⚡ Done. Processed {n} task(s).")


if __name__ == "__main__":
    main()
