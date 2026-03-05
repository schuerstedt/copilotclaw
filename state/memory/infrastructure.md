# Infrastructure

_Last updated: 2026-03-05_

## GitHub Account

- **Org**: `Copilotclaw` — this is MY org, my own GitHub account
- **Full-access PAT**: stored as `GH_TOKEN` / `COPILOT_PAT` in workflows
- **Pro subscription**: active (Marcus upgrading to Pro+ when credits run out)
- **Email**: stored in `https://github.com/Copilotclaw/private` (private repo, credentials/email.md)
- **Public repo**: `Copilotclaw/copilotclaw`
- **Private repo**: `Copilotclaw/private` — credentials, personal notes, email creds

## Secrets

| Secret | Purpose | Status |
|--------|---------|--------|
| `COPILOT_PAT` | Auth for Copilot CLI agent (full-access, org-scoped) | ✅ Working |
| `BILLING_PAT` | Same value as COPILOT_PAT; used for Copilot quota display | ⚠️ Needs "Plan" read permission added to PAT |
| `MOLTBOOK_API_KEY` | Crunch's Moltbook social network identity | ✅ Set (crunch_test_probe_xyz123 account) |
| `AZURE_ENDPOINT` | Azure AI Foundry base URL | ✅ Set by Marcus |
| `AZURE_APIKEY` | Azure AI Foundry API key | ✅ Set by Marcus |

## Moltbook

- **All accounts**: stored in `Copilotclaw/private/credentials/moltbook.json` — check there for keys

| Account | Status | Notes |
|---------|--------|-------|
| `crunchci` | ⚠️ KEY LOST | 10 karma, 2 posts. Marcus can rotate key at https://www.moltbook.com/humans/dashboard |
| `crunchclaw` | ⚠️ KEY LOST (truncated during reg) | Claim URL: https://www.moltbook.com/claim/moltbook_claim_jk_Y1Hf1br16LGsppwR58A57v9u7d_E5 — tweet "splash-QLWA" to claim |
| `crunch_test_probe_xyz123` | ✅ ACTIVE (current) | Working key in private repo + MOLTBOOK_API_KEY secret |

**To get a clean identity**: Marcus claims `crunchclaw`, rotates key at `/humans/dashboard`, updates `MOLTBOOK_API_KEY` secret.

## Workflows

- `agent.yml` — main Copilot CLI agent workflow
  - Has `pull-requests: write` permission (added 2026-03-04)
  - Does NOT have `workflows: write` — workflow file changes must be pushed from Marcus's local clone
- Heartbeat workflow — scheduled check, posts diary entry, runs CI stats, stale issue cleanup

## Known bugs fixed
- `mindepth` bug in session mapping workflow: was `mindepth 2`, fixed to `mindepth 3` (2026-03-04, issue #3)

## Stale issue housekeeping
- Heartbeat step 3: auto-closes unlabeled issues >14 days old
- `crunch/review` = in review by Marcus or Crunch — heartbeat asks for close after 7 days idle (no auto-close)
- `crunch/done` label DEPRECATED — replaced by `crunch/review`

## Azure AI Foundry

One key (`AZURE_APIKEY`) for all models. Endpoint: `AZURE_ENDPOINT`.

| Model | RPM | TPM | Quality | Notes |
|-------|-----|-----|---------|-------|
| `grok-4-1-fast-non-reasoning` | 50 | 50,000 | ⭐⭐⭐⭐⭐ | **Default** — fastest, reliable, 49/50 benchmark |
| `grok-4-1-fast-reasoning` | 50 | 50,000 | ⭐⭐⭐⭐⭐ | Same quality, 2x slower, use for hard reasoning |
| `Kimi-K2.5` | ~20 | — | ⚠️ | Flaky endpoint (content=None); avoid for now |
| `model-router` | ~20 | — | — | Needs AzureOpenAI client (not compat); 404s on compat |

**Use `grok-4-1-fast-non-reasoning` as default for all azure skill calls.**

## Model economy
- General-purpose agents default to `gpt-4.1` (free tier) to save premium quota
- Defined in AGENTS.md under "Model Economy" table
- For LLM reasoning/generation tasks: use `grok-4-1-fast-non-reasoning` via azure skill (50 RPM, cheap)
