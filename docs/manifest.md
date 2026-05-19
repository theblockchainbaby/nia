# Worker Manifest Spec — v0.1

> The `worker.yaml` file is the protocol layer of Nia. Anything that gets `nia worker install`-ed must conform to this spec. Once v0.1 ships publicly, this becomes ecosystem surface area — changes happen via additive fields with `schema_version` bumps, never by breaking existing manifests.

## Minimal valid manifest

```yaml
name: hello-world
version: 0.1.0
trigger:
  manual: true
actions:
  - id: greet
    kind: deterministic
    impl: builtin:debug.echo
    inputs:
      message: "Hello from Nia."
```

## Full spec

```yaml
# REQUIRED — identity
name: morning-ops              # kebab-case, unique within a Nia install
version: 0.1.0                 # semver
schema_version: 0.1            # manifest spec version this was written against

# OPTIONAL — metadata
description: |-
  Pull overnight email + Notion data and generate the daily brief PDF.
author: york@yorksims.com
homepage: https://yorksims.com/workers/morning-ops
license: AGPL-3.0-or-later
tags: [email, notion, daily, brief]

# REQUIRED — when this worker runs
trigger:
  # exactly one of: cron, interval, manual, event
  cron: "0 6 * * *"                       # standard cron expression, local TZ
  # interval: { minutes: 30 }             # alt: every N units
  # manual: true                          # alt: only `nia worker run X` invokes
  # event: { source: webhook, name: stripe.subscription.created }

# OPTIONAL — explicit permissions the worker needs. Used by `nia inspect`
# to show the user what surface area the worker touches before they enable it.
# Format: <service>:<scope>[:<resource>]
permissions:
  - notion:write
  - gmail:read
  - stripe:read
  - filesystem:write:~/.nia/briefs

# OPTIONAL — config the worker reads from. User overrides via
# ~/.nia/workers/<name>/config.yaml. Defaults live here.
config:
  accounts:
    - you@example.com
    - team@example.com
  output_dir: ~/.nia/briefs
  brief_recipient: "+15551234567"

# REQUIRED — the actions this worker performs in order.
actions:
  - id: sweep-email                       # unique within this manifest
    kind: deterministic                   # deterministic | judgment
    impl: builtin:email.sweep_inbox       # builtin:<module>.<fn> OR file:<path>:<fn>
    inputs:
      accounts: "{{ config.accounts }}"   # templating: config, env, prior actions
      since: 24h
    # OPTIONAL — when to skip this action
    when: "true"                          # expression. defaults to "true"
    # OPTIONAL — timeout in seconds. default 30
    timeout: 60
    # OPTIONAL — retry policy
    retry:
      attempts: 3
      backoff: exponential                # exponential | linear | none

  - id: classify-unknowns
    kind: judgment                        # invokes an LLM
    impl: builtin:llm.classify
    # judgment actions REQUIRE a `condition` field. The runtime only invokes
    # an LLM when this evaluates true. Cheap workers will frequently skip
    # every judgment step.
    condition: "actions.sweep-email.results.unmatched | length > 0"
    inputs:
      model: claude-haiku-4-5
      candidates: "{{ actions.sweep-email.results.unmatched }}"
      categories: [job-reply, customer, vendor, newsletter, other]
    # OPTIONAL — for judgment steps, a max-cost guard. Aborts the run if
    # the projected cost exceeds this. Default: no cap.
    cost_ceiling_usd: 0.05

# OPTIONAL — outputs the run produces. Used by `nia inspect` to summarize
# what artifacts this worker creates.
outputs:
  - id: brief-pdf
    description: Daily brief PDF
    path: ~/.nia/briefs/{date}.pdf
  - id: notion-updates
    description: Reminder + Deal updates written to Notion
    counter: actions.*.results.notion_writes | sum
```

## Field semantics

### `kind: deterministic`
The action's `impl` is a pure-code function. No LLM call. Idempotent if at all possible. Failures are programmer errors and should be raised, not handled by retrying with a different model.

### `kind: judgment`
The action invokes an LLM (or, in future, any model/human-review surface). **Required** to declare a `condition` — the runtime refuses to load manifests where a judgment step has no condition. The condition exists so runs can skip judgment entirely when the deterministic context doesn't need it. This is the cost-savings architecture in protocol form.

### `condition` expressions
Subset of Jinja-like expression language:
- `actions.<id>.results.<key>` — access prior action outputs
- `config.<key>` — access manifest config
- `env.<NAME>` — access env vars
- Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`, `in`, `| length`
- No function calls, no side effects, no arbitrary Python. Parsed at load-time and rejected if malformed.

### `impl` syntax
- `builtin:<module>.<fn>` — ship in `nia.workers._builtins`. Hand-audited.
- `file:<relpath>:<fn>` — Python file inside the worker directory. Loaded with restricted import scope (no network unless declared in `permissions`).

### `permissions`
Declarative, used by `nia inspect` to show users what the worker touches **before** enabling. In v0.1 they are advisory (the runtime does not enforce them). In v0.2+ they will be enforced via OS-level adapters (Keychain scope, sandbox, etc.).

## What the runtime guarantees

1. **A judgment step never runs if its condition is false.** No exceptions.
2. **Manifest is parsed once at load time.** Malformed manifests fail before any action executes.
3. **Every action emits a structured result.** Results are persisted in run state for `nia inspect` and downstream `condition` evaluation.
4. **A worker can be `dry-run` at any time.** All side effects mocked; the run produces the same shape of results but writes nothing.

## What the runtime explicitly does NOT do (in v0.1)

- Enforce `permissions` (advisory only — see above)
- Provide a worker marketplace beyond `git clone` (v0.2)
- Support remote/cloud workers (v0.3+, opt-in)
- Manage cross-worker dependencies (workers are isolated by design)

## Versioning

`schema_version` MUST be set. When the spec changes in a breaking way, this version bumps and the runtime can refuse to load manifests targeting a higher schema than it understands. Additive fields do not bump the schema version.
