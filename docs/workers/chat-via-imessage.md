# Worker: `chat-via-imessage` (planned, v0.2)

> The worker that lets York text Nia and get answers — **using his Claude Max plan**, not API tokens.

## The thesis

Most agent products force you into their cloud chat UI. Nia inverts: you text from your existing iMessage app, you get answers in the same conversation thread, and the reasoning is your existing Claude Max subscription.

## Architecture

```
trigger:
  interval:
    seconds: 30          # poll cadence

actions:
  - id: poll-imessage          [deterministic]
    impl: builtin:imessage.poll_new
    inputs:
      chat_db: ~/Library/Messages/chat.db
      from_allowlist:
        - you@example.com
      since_seconds: 60

  - id: think
    [judgment]                  # spawns `claude` CLI, NOT the API
    condition: actions.poll-imessage.results.new_count > 0
    impl: builtin:llm.claude_max_oneshot
    inputs:
      messages: "{{ actions.poll-imessage.results.messages }}"
      session_dir: ~/.nia/sessions/chat-via-imessage
      model_hint: sonnet         # cheap default; bump to opus for hard asks

  - id: reply
    [deterministic]
    condition: actions.think.results.response | length > 0
    impl: builtin:imessage.reply_via_shortcut
    inputs:
      shortcut_name: "Send Text"
      text: "{{ actions.think.results.response }}"
```

## Why this is a Nia-shaped worker, not a daemon rebuild

The existing `start_imessage_channel.sh` keeps a persistent `claude --channels` process running. That works but:
1. Requires a terminal session open
2. Burns CPU continuously (your fan concern)
3. No state visibility — black-box

The worker model is better because:
- **Inspectable**: `nia inspect worker chat-via-imessage` shows trigger, last responses, judgment cost
- **Auditable**: every reply lives in `~/.nia/runs/chat-via-imessage/*.json`
- **Cheap idle**: 30-second polls when no traffic ≈ free
- **Same Max plan path**: spawns `claude` CLI under your logged-in account, no tokens

## Required builtins to build

1. **`builtin:imessage.poll_new`** — reads `~/Library/Messages/chat.db` (SQLite, read-only), filters by sender allowlist, filters by `since_seconds`, returns list of `{from, text, date_iso, chat_id}`. The hard part is the SQL — Messages stores text as compressed BLOBs in newer macOS versions.

2. **`builtin:llm.claude_max_oneshot`** — `subprocess.run(["claude", "-p", text, "--output-format", "json"])`, parses response, returns `{response: str, model_used: str}`. Optional `session_dir` for continuity across messages.

3. **`builtin:imessage.reply_via_shortcut`** — already 90% done; reuse the text-shortcut path from `imessage.send_pdf` (the `_shortcuts_run` helper).

## Risks / gotchas to plan for

- **Permissions**: Reading `chat.db` requires Full Disk Access for the parent process. From launchd this is per-binary — need to grant `~/nia/.venv/bin/nia` Full Disk Access in System Settings → Privacy & Security.
- **Encoding**: Recent macOS stores message text in `attributedBody` (a typedstream BLOB) instead of plain `text` column. Need to parse it. Python has `pytypedstream` or hand-rolled extraction.
- **Latency**: 30-second polling means ≤30s response latency. For interactive feel, drop to 10s. CPU still negligible.
- **Loop safety**: Filter out replies the worker just sent (otherwise it could process its own outbound messages as new inbound). Track last reply timestamp.
- **Conversation context**: First version is stateless (every reply is a fresh `claude -p` call). v0.2 of this worker adds `--resume` session IDs for continuity.

## Why this is NOT a token-cost story

The `claude` CLI subprocess invocation hits Anthropic via the **logged-in account** (York's Max plan). It does not need `ANTHROPIC_API_KEY` set. It's the same path as opening `claude` interactively. Max plan covers unlimited usage at standard rate limits.

## Timeline

- **Sat/Sun May 17-18**: build + test
- **Weekday slot**: not necessary — the manual `start_imessage_channel.sh` still works as a fallback while this is being built.

## Open questions to resolve before build

- Polling interval: 10s vs 30s vs 60s?
- Default model: sonnet vs haiku? (haiku is faster + cheaper Max-quota-wise, sonnet is smarter)
- How to handle group chats / non-allowlist senders? (v0.1: ignore entirely)
- Should the worker auto-create a Notion task when York asks something that requires action? (v0.2 nice-to-have)
