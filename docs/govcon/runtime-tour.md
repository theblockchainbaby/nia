---
title: Nia, in sixty seconds
subtitle: Six commands, six beats, the whole runtime
author: York Sims, Founder, Caipher AI
date: 2026-06-12
---

# The whole runtime in six commands

```bash
nia worker list              # six bundled workers
nia inspect worker hello-world
nia dry-run worker hello-world
nia worker run hello-world
nia logs hello-world
cat workers/hello-world/worker.yaml
```

# Six beats, ten seconds each

| Time | Command | What it says |
|------|---------|--------------|
| 0:00 | `nia worker list` | Six bundled workers. Each one is a declarative manifest, not a script. |
| 0:10 | `nia inspect worker hello-world` | Every action, every condition, every recent run. No black box. |
| 0:20 | `nia dry-run worker hello-world` | Same executor. Side effects mocked. You see what it WOULD do, before you let it do anything. |
| 0:30 | `nia worker run hello-world` | Now for real. Every result is persisted. |
| 0:40 | `nia logs hello-world` | Audit trail is not bolted on. It is the product. |
| 0:50 | `cat workers/hello-world/worker.yaml` | About 850 lines of runtime behind a manifest you can read in 20 seconds. Two runtime dependencies. AGPL. On GitHub. |

# The structural rule, in one paragraph

Every action in a manifest has a `kind`. `kind: deterministic` is plain code. `kind: judgment` is the only kind permitted to invoke a language model. The manifest loader refuses to parse a judgment action that lacks a `condition:` predicate. The predicate is evaluated against the persisted results of prior actions in the same run. The runtime then invokes the model only when the predicate is true. The rest of the time, the model branch is declared, gated, and dark.

# The hello-world manifest in full

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

The `greet` action is deterministic and runs. The `maybe-think` action is `kind: judgment` and its condition is never true, so the model step never executes. The branch exists, it is declared, and it stays dark. That is not an error path or a fallback. It is the expected path. The bundled `morning-ops` and `notion-sync` workers ship with no judgment steps at all.

---

**York Sims**
Founder, Caipher AI
github.com/theblockchainbaby/nia
