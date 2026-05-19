# Nia: architecture and design

Most automation that touches an LLM calls one on every step. That is expensive, it is unreliable, and it is hard to audit. Nia is built on the opposite assumption. Deterministic by default. AI only when needed.

This document explains where that idea came from and how the runtime enforces it.

## The $5 morning

I had a small automation that ran at 3 AM. It swept two email accounts, pulled my open reminders out of Notion, rendered a one page brief as a PDF, and sent it to my phone before I woke up. Useful. I relied on it.

It was also built the way most "AI agent" tooling tells you to build things: a model in the loop at every step. The model decided how to summarize the inbox. The model decided which reminders mattered. The model formatted the output. It worked, and it cost about $5 a day in API tokens.

Five dollars a day is $1,800 a year to do a job that, when I looked closely, almost never required a model at all. Sorting messages by sender is a dictionary lookup. Pulling open reminders is a database query. Rendering a PDF is a template. None of that is judgment. It is just code. The only step that genuinely needed a model was classifying the occasional unrecognized sender, and most mornings there were none.

So I was paying a language model to do arithmetic.

## The inversion

Nia is a local operations runtime. The unit of work is a worker: a manifest, a `worker.yaml` file, that declares when it runs and the ordered list of actions it performs.

Every action has a `kind`. There are two.

`kind: deterministic` is plain code. A function. It does not call a model. It is idempotent where possible, it is fast, and when it fails it fails like a bug, not like a bad guess.

`kind: judgment` is the step that invokes a model. And here is the rule the runtime enforces: a judgment action must declare a `condition`. The runtime refuses to load a manifest where a judgment step has no condition. The model is invoked only when that condition evaluates true against the results the deterministic steps already produced.

That single constraint is the whole design. The expensive, non-deterministic part of the system is not the default. It is a declared exception, gated by a boolean, and most of the time the boolean is false.

## What a worker looks like

Here is `hello-world`, the smallest worker in the repo, shown in full. It still carries the whole idea.

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
    condition: "actions.greet.results.echoed == 'never'"
    impl: builtin:debug.echo
    inputs:
      message: "(this LLM step is skipped)"
```

`greet` is deterministic: it calls a builtin and returns. `maybe-think` is `kind: judgment`. Its `condition` checks whether `greet` echoed the literal string `never`, which it never does, so the judgment step is skipped on every run. The branch exists, it is declared, and it stays dark.

That is not an error path or a fallback. It is the expected path. A judgment step runs only when its condition is true, and a well designed worker arranges for that to be rare. The bundled `morning-ops` and `notion-sync` workers ship with no judgment steps at all. They are deterministic from end to end, and they cost nothing to run.

## The runtime guarantees

A design is only worth as much as the runtime that holds the line on it. Nia guarantees four things.

1. A judgment step never runs when its condition is false. No exceptions, no edge cases.
2. The manifest is parsed once, at load time. A malformed worker fails before a single action executes, not halfway through.
3. Every action emits a structured result. Those results are persisted, which is what makes both condition evaluation and inspection possible.
4. Any worker can be dry-run. Every side effect is mocked. The run produces the same shape of results and writes nothing.

## Reading a worker's mind

Two commands matter more than the rest.

`nia inspect worker <name>` prints the trigger, every action, the exact condition on every judgment step, and the recent run history with timings and failures. Most automation that involves a model is a black box. You hand it your inbox and you hope. A worker you can inspect in a fraction of a second is a different kind of object. You can reason about it. You can defend it to someone else.

`nia dry-run worker <name>` executes the worker for real, with every side effect mocked. It is how you vet a worker before you let it write to your actual Notion, your actual inbox, your actual Stripe account. If you can dry-run it, you can audit it. If you can audit it, you can trust it.

These are not features bolted on at the end. Auditability is the product.

## Repository layout

```
nia/
  runtime/     manifest loader, condition evaluator, executor, registry, run state
  workers/     bundled workers, plus the builtin action library
  adapters/    OS-specific glue: macOS (launchd, iMessage) today, Linux in progress
  memory/      local run-state persistence
  cli/         the nia command
docs/          this document and the manifest spec
```

## What v0.1 is, and is not

Nia v0.1 is deliberately small.

It is a runtime, a CLI, a manifest spec, a macOS adapter, and three reference workers. It has two runtime dependencies. It is AGPL. It runs on your laptop, it owns nothing, and it costs almost nothing.

It is not a marketplace. It is not a cloud service. It is not a web dashboard. There is no Windows support. The Linux adapter is stubbed and honest about being stubbed. The judgment tier is defined by the manifest grammar and enforced by the runtime, and the bundled workers do not exercise it, because they do not need to. That is the thesis working as intended.

I would rather ship a small thing that is true than a large thing that is impressive.

## Where this goes

The manifest is the protocol. Once v0.1 is public it is ecosystem surface area, and it changes only by adding fields, never by breaking what already runs.

The runtime is open. The repo is open. If you build automation that touches a model, I think you are probably paying a model to do arithmetic too, and I would like to see what you build when it stops.
