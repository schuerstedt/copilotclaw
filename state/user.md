# User Profile

## Identity

- **Name**: Marcus
- **GitHub handle**: schuerstedt
- **How to address them**: Marcus

## Preferences

- **Tone**: Casual and chatty. Types informally. No over-formality needed.
- **Response style**: Conversational, a bit playful is fine. Skip the corporate filler.
- **Things they care about**: Keeping premium AI quota costs down. Experimenting and exploring capabilities.

## Context

- **What they're building**: Exploring what Crunch (the CI agent) can do. Building skills and infra as we go.
- **Tools / stack they use**: GitHub Actions, gh CLI, gitclaw repo.
- **Anything else Crunch should know**: |
  - Has a cat: AIGEGE (AGG) — long-haired silver tabby, named after Marcus's Chinese wife. 爱格格 = "beloved princess" (Qing dynasty noble title). When he calls the cat, his wife smiles. Chinese wife = happy life. 🥰
  - Wants an email skill eventually (hinted in issue #7).
  - Needs to: add BILLING_PAT to agent.yml + "Plan" read permission to COPILOT_PAT for quota display.

## Skills Built Together

| Skill | What it does | Built |
|-------|-------------|-------|
| `funnysum` | Sums two numbers with a math joke | 2026-03-04 issue #3 |
| `model-switch` | Switch model tiers (premium/standard/free) | 2026-03-04 issue #6 |
| `session-stats` | Stats footer: CI times + Copilot quota | 2026-03-04 issue #6 |

## History of Notable Actions

- Fixed `mindepth` bug in session-mapping workflow (issue #3)
- Implemented Model Economy in AGENTS.md — general-purpose defaults to gpt-4.1
- Built premium-usage.sh script + wired BILLING_PAT into workflow

---

_Last updated: 2026-03-04_
