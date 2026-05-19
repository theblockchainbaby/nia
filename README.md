# Nia

**Deterministic by default. AI only when needed.**

Nia is a local operations runtime. Workers run on triggers or schedules, execute deterministic actions against your services (email, Notion, Stripe, GitHub, …), and only invoke an LLM when something genuinely needs judgment. Runs on your laptop, owns nothing, costs almost nothing.

---

## Install

```bash
curl -fsSL https://nia.run/install | bash
```

Or from source:

```bash
git clone https://github.com/theblockchainbaby/nia
cd nia
pip install -e .
```

## Five-minute tour

```bash
nia worker list                          # see what's installed
nia worker install morning-ops           # install a worker from the built-in registry
nia inspect worker morning-ops           # read its mind: triggers, actions, judgment conditions
nia dry-run worker morning-ops           # execute with all side effects mocked
nia worker enable morning-ops            # schedule it
nia status                               # what's running, last run times, next runs
nia logs morning-ops                     # tail the run history
```

## Why a runtime instead of an agent?

Most "AI agent" products are black boxes that call an LLM on every step. They are:

- expensive (every action burns API tokens)
- unreliable (one model hiccup and the whole chain collapses)
- opaque (you can't audit what they're about to do)
- hard to defend in production (security, compliance, debugging)

Nia inverts the model. A worker is a manifest of explicit **actions** — most of which are pure code. The LLM is invoked only at points the worker marks as **judgment** steps, and only when an explicit condition triggers. Most workers ship with zero judgment steps. They are deterministic from end to end.

You get:

- **Lower cost** — the morning brief that used to cost $5/day in API tokens now costs $0
- **Auditability** — `nia inspect` shows you every action, every judgment condition, every recent run
- **Reliability** — deterministic actions don't hallucinate
- **Reversibility** — `nia dry-run` lets you preview side effects before allowing real writes

## What a worker looks like

```yaml
# workers/morning-ops/worker.yaml
name: morning-ops
version: 0.1.0
description: Pull overnight email + Notion, generate a daily brief PDF.
trigger:
  cron: "0 6 * * *"
permissions:
  - notion:read
  - gmail:read
  - filesystem:write:~/.nia/briefs
actions:
  - id: sweep-email
    kind: deterministic
    impl: builtin:email.sweep_inbox
    inputs:
      accounts: [you@example.com, team@example.com]
      since: 24h
  - id: pull-notion-reminders
    kind: deterministic
    impl: builtin:notion.due_reminders
  - id: classify-unknowns
    kind: judgment
    condition: actions.sweep-email.results.unmatched > 0
    impl: builtin:llm.classify
    inputs:
      model: claude-haiku-4-5
      categories: [job-reply, customer, vendor, newsletter, other]
  - id: render-brief
    kind: deterministic
    impl: builtin:render.pdf
    inputs:
      template: builtin:morning-brief.md
      output: ~/.nia/briefs/{date}.pdf
```

`kind: deterministic` runs pure code. `kind: judgment` invokes an LLM, but only when the `condition` evaluates true. Most runs will skip every judgment step.

## Reference workers

Five workers ship in the repo as both reference implementations and useful day-one tools:

- **morning-ops** — overnight email + Notion → daily brief PDF
- **notion-sync** — sent/received email + git commits + Stripe events → Notion CRM
- **inbox-triage** — classify inbound, flag unanswered > 24h, escalate substantive replies
- **stripe-digest** — daily subscription movement, MRR, churn signals
- **github-review** — PRs needing your review, stale branches, CI failures

Each runs locally. Each is deterministic-first. Each is auditable via `nia inspect`.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system design. The short version:

- **Runtime core** — manifest loader, action dispatcher, judgment escalation, run state capture
- **Workers** — folders containing `worker.yaml` + optional helper code
- **Adapters** — OS-specific bits (Mac: launchd + iMessage. Linux: systemd + signal-cli)
- **Memory** — local JSON state for last-run markers, dedup sets, run history

Three runtime dependencies. No AI framework. No orchestration sprawl. Designed to feel like `systemd` or `cron`, not LangChain.

## Status

**v0.1.0 — May 2026.** Pre-release. Manifest spec is locked. Mac adapter works. Linux adapter minimum-viable. Worker registry is `git clone`-based; a richer install mechanism comes in v0.2.

## License

[AGPL-3.0-or-later](LICENSE). Forks that ship Nia as a hosted service must publish their source.

---

Built by [York Sims](https://yorksims.com). Nia runs Caipher AI LLC's operations in production 24/7 — every release ships only after running clean for at least 7 days against real workloads.
