# Nia

**Deterministic by default. AI only when needed.**

Nia is a local operations runtime. Workers run on triggers or schedules, execute deterministic actions against your services (email, Notion, Stripe, GitHub, …), and only invoke an LLM when something genuinely needs judgment. Runs on your laptop, owns nothing, costs almost nothing.

---

## Install

```bash
git clone https://github.com/theblockchainbaby/nia
cd nia
pip install -e .
```

Requires Python 3.10+. The core runtime has two dependencies, PyYAML and rich.
Optional extras pull in only what a given worker needs:

```bash
pip install -e ".[render]"     # workers that render PDFs
pip install -e ".[judgment]"   # workers with LLM judgment steps
```

macOS is fully supported (launchd, iMessage). The Linux adapter is in progress.

## Five-minute tour

```bash
nia worker list                       # list available workers
nia inspect worker hello-world         # show its triggers, actions, conditions, recent runs
nia dry-run worker hello-world         # execute it with all side effects mocked
nia worker run hello-world             # run it once, for real
nia status                             # runtime status and recent runs
nia logs hello-world                   # tail recent runs for this worker
```

Every command above works on a clean install. `hello-world` is the bundled smoke-test worker. `nia worker install` and `nia worker enable` also exist, but in v0.1 they print setup instructions rather than acting on their own; automated registry install and scheduling land in v0.2.

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

This is the complete `hello-world` worker that ships in the repo:

```yaml
name: hello-world
version: 0.1.0
schema_version: 0.1
description: |-
  Smoke-test worker. Demonstrates a deterministic action and a judgment
  action whose condition is never true, so the LLM step is always skipped.
author: york@yorksims.com
license: AGPL-3.0-or-later
tags: [demo, smoke-test]

trigger:
  manual: true

config:
  greeting: "Hello from Nia."

actions:
  - id: greet
    kind: deterministic
    impl: builtin:debug.echo
    inputs:
      message: "{{ config.greeting }}"

  - id: maybe-think
    kind: judgment
    # Will never fire — the demonstration is that judgment is GATED, not
    # invoked-by-default. This is the architectural thesis in worker form.
    condition: "actions.greet.results.echoed == 'never'"
    impl: builtin:debug.echo
    inputs:
      message: "(this LLM step is skipped)"
```

It is the smallest worker in the repo, and it still carries the whole idea. `greet` is `kind: deterministic`: pure code, no model. `maybe-think` is `kind: judgment`, but its `condition` is never true, so the step is skipped on every run. Judgment is declared, conditional, and skipped by default. The bundled `morning-ops` and `notion-sync` workers have no judgment steps at all.

See [docs/manifest.md](docs/manifest.md) for the full manifest spec.

## Reference workers

Three workers ship in the repo, as both reference implementations and working tools:

- **hello-world** — smoke test: one deterministic action, one gated judgment action
- **morning-ops** — overnight email and open Notion reminders, rendered to a daily brief PDF
- **notion-sync** — sent and received email, new git commits, and Stripe events, synced into Notion

Each runs locally. Each is deterministic-first. Each is auditable via `nia inspect`.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system design. The short version:

- **Runtime core** — manifest loader, condition evaluator, action executor, run-state capture
- **Workers** — folders containing `worker.yaml` + optional helper code
- **Adapters** — OS-specific bits (macOS: launchd + iMessage; Linux: systemd + signal-cli, planned)
- **Memory** — local JSON state for last-run markers, dedup sets, run history

Two runtime dependencies. No AI framework. No orchestration sprawl. Designed to feel like `systemd` or `cron`, not LangChain.

## Status

**v0.1.0 — May 2026.** Pre-release. The manifest spec is locked. The macOS adapter works. The Linux adapter is stubbed. Worker install is `git clone`-based; a richer install mechanism comes in v0.2.

## License

[AGPL-3.0-or-later](LICENSE). Forks that ship Nia as a hosted service must publish their source.

---

Built by [York Sims](https://yorksims.com). The `morning-ops` and `notion-sync` workers in this repo are the ones I built Nia to run: my own morning brief and CRM sync.
