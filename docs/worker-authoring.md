# Worker Authoring Guide

A worker is a YAML manifest. This is everything you need to write one.

## The smallest valid worker

```yaml
name: hello
version: 0.1.0
schema_version: 0.1
trigger:
  manual: true
actions:
  - id: greet
    kind: deterministic
    impl: builtin:debug.echo
    inputs:
      message: "Hello from my worker."
```

Save as `nia/workers/hello/worker.yaml`. Run it:

```bash
nia worker list                # confirms it's registered
nia inspect worker hello       # shows the actions and any prior runs
nia dry-run worker hello       # executes with side effects mocked
nia worker run hello           # executes for real
nia logs hello                 # shows the run history
```

Every command above works on a fresh install with no other configuration.

## Required fields

| Field | Required | Notes |
|---|---|---|
| `name` | yes | kebab-case, unique in this Nia install |
| `version` | yes | semver |
| `schema_version` | yes | spec version this manifest was written against. `0.1` today. |
| `trigger` | yes | exactly one of: `manual: true`, `cron: "<expr>"`, `interval: {minutes: N}`, `event: {source, name}` |
| `actions` | yes | a list with at least one action |

## Optional metadata

```yaml
description: |-
  What this worker does and why someone would run it.
author: you@example.com
homepage: https://example.com/workers/hello
license: AGPL-3.0-or-later
tags: [demo, notion]
permissions:
  - notion:read
  - imap:read
  - filesystem:write:~/.nia/briefs
config:
  some_key: default_value
```

`config:` defaults appear here. Users override per worker by editing `~/.nia/workers/<worker>/config.yaml` after installing.

## The two action kinds

### Deterministic actions

`kind: deterministic` is plain code. It executes whenever its `when:` expression is true (the default is `true`, meaning it always runs).

```yaml
actions:
  - id: pull-data
    kind: deterministic
    impl: builtin:email.sweep_recent
    inputs:
      accounts: "{{ config.accounts_file }}"
      since_hours: 24
```

### Judgment actions

`kind: judgment` is the only action kind that may invoke a language model. The runtime refuses to load a worker whose judgment action has no `condition:` field. The model is invoked only when that condition evaluates true against the persisted results of prior actions in the same run.

```yaml
actions:
  - id: classify
    kind: judgment
    condition: "actions.pull-data.results.count > 0"
    impl: builtin:claude.classify
    inputs:
      items: "{{ actions.pull-data.results.items }}"
      categories: ["customer", "vendor", "other"]
```

If `count` is zero, the LLM is not invoked. The CLI surfaces this as `status: skipped, reason: judgment condition false - LLM not invoked`. That is the structural property Nia stakes.

## Templating

`{{ ... }}` substitutes from the run context. Three sources are exposed:

| Source | Example | Notes |
|---|---|---|
| `config.*` | `{{ config.accounts_file }}` | Worker's `config:` block, after user overrides. |
| `env.*` | `{{ env.HOME }}` | Process environment. Use for secrets via env vars, not the manifest. |
| `actions.<id>.results.*` | `{{ actions.pull-data.results.items }}` | Earlier action results, in order. |

Inputs can be strings, lists, or dicts; the template engine recurses into them.

## Built-in actions available

| Impl | Purpose | Dry-run safe? |
|---|---|---|
| `builtin:debug.echo` | Echo a message. Useful for smoke tests. | yes |
| `builtin:email.sweep_recent` | Pull recent inbox + sent activity across IMAP accounts. | yes (returns mock) |
| `builtin:notion.due_reminders` | Query open reminders from a Notion DB. | yes (returns mock) |
| `builtin:notion.email_sync` | Sync sent/received email into Notion. | yes |
| `builtin:notion.git_sync` | Sync git repo state into Notion. | yes |
| `builtin:notion.stripe_sync` | Sync Stripe subscription events into Notion. | yes |
| `builtin:render.morning_brief_pdf` | Render a daily brief PDF. | yes |
| `builtin:imessage.send_pdf` | Deliver a file via iMessage (macOS only). | yes (no send) |
| `builtin:claude.classify` | Classify a batch of items into a category list. **The only judgment-class builtin today.** | yes (no API call) |

Every builtin honors `context.get("dry_run")` and returns representative mock output without performing the side effect. `nia dry-run worker <name>` exercises this path.

## Writing a new builtin

Builtins live at `nia/workers/_builtins/<module>.py`. The signature is:

```python
def my_action(*, inputs: dict, context: dict) -> dict:
    """One-line summary of what this action does.

    Inputs:
      foo: ...
      bar: ...

    Returns:
      {"key": ...}
    """
    if context.get("dry_run"):
        return {"key": "mock-value", "dry_run": True}

    # Real implementation here.
    ...
    return {"key": real_value}
```

Refer to it from a worker as `builtin:my_module.my_action`.

The contract:

- Inputs are dicts. Templated expressions are already resolved.
- Return a dict. The executor wraps non-dict returns as `{"value": ...}`.
- Read `context["dry_run"]` and return mock data when true. **Never call a real service on a dry-run.**
- Raise an exception on real errors. The executor will record the action as failed and stop the run.

## Testing your worker

```python
# tests/test_my_worker.py
import yaml
from nia.runtime.manifest import parse_manifest
from nia.runtime.executor import execute


def test_worker_loads():
    with open("nia/workers/my-worker/worker.yaml") as f:
        manifest = parse_manifest(yaml.safe_load(f))
    assert manifest.name == "my-worker"


def test_worker_dry_runs_clean():
    with open("nia/workers/my-worker/worker.yaml") as f:
        manifest = parse_manifest(yaml.safe_load(f))
    run = execute(manifest, dry_run=True)
    assert run.status.value == "success"
    for action in run.actions:
        assert action.status.value in ("success", "skipped")
```

Run with `uv run pytest tests/test_my_worker.py`.

## Deploying under launchd (macOS)

Until v0.2 lands automated install, you write a launchd plist by hand. Pattern:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nia.my-worker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>set -a; source $HOME/.nia/env; set +a; /path/to/nia/.venv/bin/nia worker run my-worker</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/nia</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/you/.nia/logs/my-worker_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/you/.nia/logs/my-worker_stderr.log</string>
</dict>
</plist>
```

Save at `~/Library/LaunchAgents/com.nia.my-worker.plist`, then:

```bash
launchctl load ~/Library/LaunchAgents/com.nia.my-worker.plist
launchctl list | grep nia    # confirm it's loaded
```

Sourcing a `.env` file before running `nia` lets you keep secrets (Anthropic API key, Notion token, IMAP passwords) out of the plist itself.

## Discipline

Three rules to keep your worker honest:

1. **Default to deterministic.** If you can write it as a function, write it as a function. Save `kind: judgment` for the steps that need a model.
2. **Make the judgment condition narrow.** The whole point is that the model runs rarely, and only when the deterministic steps have already isolated the cases that need it.
3. **Read the run history.** `nia logs <worker>` and the JSON files at `~/.nia/runs/<worker>/<id>.json` are the audit surface. If you ever wonder what your worker actually did, look there. If the run history is illegible, your manifest is over-engineered.

## What's not in v0.1 yet

| Feature | Status |
|---|---|
| `nia worker install <name>` from a registry | v0.2 |
| `nia worker enable <name>` writes the launchd plist for you | v0.2 |
| Soft permission enforcement (action's used imports match worker's permissions) | v0.2 |
| Parallel actions in a worker | v0.3 |
| Retry/timeout enforcement | v0.3 |
| Linux adapter | stubbed |
| Windows adapter | not started |
