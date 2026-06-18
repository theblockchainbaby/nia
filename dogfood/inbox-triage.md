# inbox-triage observation log

Public field notes from running the `inbox-triage` worker continuously
under launchd on the founder's daily workstation. This worker is the
first one Nia ships that exercises the gated LLM path (`kind: judgment`
with a manifest-declared `condition:`), so the runtime invariant the
architecture document stakes is either empirically true here or it is
not.

Append only. Each observation has a class:

- **gate** — did the condition gate fire correctly (LLM invoked iff condition true)
- **cost** — token usage and dollar cost per gated invocation
- **classification** — does the model classify reasonably or fabricate categories
- **latency** — wall-clock per call
- **continuity** — does run history persist across boots / process restarts
- **credentials** — service auth state for the deterministic inputs

Discipline: one observation is noise. Wait for a cluster of roughly 5 in
the same class before changing anything. When a cluster forms, replay
through the canonical cycle before touching live behavior.

***

## 2026.06.17 PDT · gate (the architectural claim is empirically true)

**Situation:** Four days of hourly launchd-scheduled runs of inbox-triage on yorksims@gmail.com production inbox. 112 run records in `~/.nia/runs/inbox-triage/`. The gate condition is `actions.sweep-recent.results.unanswered_count > 0`, evaluated against the persisted result of the prior deterministic sweep. The runtime claim under test: when the condition is false, the LLM is structurally not invoked.

**What it did:** Across the 112 runs, the executor recorded the classify action as `skipped` on 41 runs with the literal reason string `judgment condition "actions.sweep-recent.results.unanswered_count > 0" false — LLM not invoked`. On those 41 runs the Anthropic client was not constructed, no network call was made, and no tokens were billed. The skip is observable in `~/.nia/runs/inbox-triage/*.json` action records; every skipped record carries the condition expression verbatim and the false evaluation.

**Reaction:** The architectural claim is not a paper claim here. The gate is observable on disk. A formal methods reviewer reading this repository can grep `~/.nia/runs/inbox-triage/*.json` for `"status": "skipped"` and count the proofs themselves. 41 of 41 gate-skipped runs produced zero tokens; the runtime is faithful to the manifest grammar.

**Note:** This is the v0.2.0 thesis demonstration end to end. Together with the `hello-world` `maybe-think` action (whose condition is never true and whose LLM is never invoked across the entire test suite), the gate has been empirically demonstrated in both directions in production telemetry. The Phase I research is to lift this from "observable on disk" to "mechanically verified."

## 2026.06.17 PDT · credentials (silent secondary failure)

**Situation:** The inbox-triage worker is configured for two IMAP accounts in `~/.nia/workers/inbox-triage/accounts.yaml` (a symlink to morning-ops accounts). The `yorksims` account is the operator's primary Gmail; the `vitros` account is a secondary mailbox.

**What it did:** 27 of the 112 runs recorded a `vitros` IMAP `AUTHENTICATIONFAILED` while still returning success for the run as a whole, because the email builtin handles per-account failures as warnings and continues on the surviving accounts. The yorksims account returns full data (inbox count, unanswered set, sent count) on the same runs that vitros silently fails.

**Reaction:** The deterministic layer behaves the way the architecture document promises: a single bad input does not poison the run. The downside is that a silently failing account does not surface anywhere a human sees it. A reviewer reading `nia logs inbox-triage` sees nothing wrong; only direct inspection of the run JSON reveals the failure.

**Note:** Credentials class, not a thesis-relevant defect. Fix is to either rotate the vitros password or drop the account from accounts.yaml. Logging only here; resolution is a configuration task, not a runtime change.

## 2026.06.17 PDT · cost (zero tokens spent so far, for a non-thesis reason)

**Situation:** The mediated judgment step has never invoked Anthropic at all in 4 days of production. Token totals across 112 runs: 0 in, 0 out.

**What it did:** Two distinct failure modes prevented every real-call attempt:

1. **10 runs** failed with `RuntimeError: anthropic package not installed`. The launchd plist invokes `/Users/york/nia/.venv/bin/nia`, but the venv was originally installed without the `[judgment]` optional dependency that pulls in `anthropic>=0.40`. The judgment-class builtin imports `anthropic` lazily inside the real-call code path (the dry-run path does not), so the missing package surfaces only at the moment the gate opens.
2. **60 runs** failed with `RuntimeError: ANTHROPIC_API_KEY environment variable is not set`. After the `anthropic` package was installed, the env source `/Users/york/MoltBot/.env` did not yet contain `ANTHROPIC_API_KEY`. The launchd-spawned bash inherits no shell environment of its own, so the key has to be in the sourced .env or the call fails fast.

**Reaction:** Two independent configuration gaps, both surfaced through the same code path: the moment the gate opens. The condition-gating layer was not at fault on any of these 70 runs. The deterministic sweep had populated `unanswered_count > 0`, the executor correctly recognized the gate as true and dispatched to the judgment action, and the judgment action correctly raised at the configuration boundary instead of silently proceeding. This is the behavior the design wants: the runtime is honest about failure right at the capability boundary, not 30 seconds in.

**Note:** Both gaps are now fixed in the running configuration as of 2026.06.17. `anthropic` 0.109.1 is installed in the venv; `ANTHROPIC_API_KEY` is in `/Users/york/MoltBot/.env`. The next launchd cron firing that satisfies the condition is expected to produce the first real classification on record. That run will be appended to this log when it lands. Do not edit this entry retroactively; the historical record is what it is.

## 2026.06.17 PDT · gate (zero false positives over 70 attempted invocations)

**Situation:** In addition to the 41 cleanly-skipped runs (gate evaluated false, LLM not invoked), the dataset also contains 70 runs where the gate evaluated true (`unanswered_count > 0`) and the executor dispatched to the judgment action, which then failed at the configuration boundary as described in the cost entry above.

**What it did:** On every one of those 70 runs the failure happened inside the judgment action's implementation function, NOT before the gate was evaluated. The executor's dispatch decision was correct in 70 of 70 cases. The 41 false-condition runs and 70 true-condition runs together comprise 111 of the 112 production runs; the remaining run is a one-off CLI dry-run from the initial deploy.

**Reaction:** The condition evaluator has been exercised against real production data for 4 days, in both directions, 111 times, with zero observable inversions. This is not a proof, but it is the empirical baseline a mechanized proof can be calibrated against. The Phase I formal model will need to recover exactly this dispatch behavior.

**Note:** Gate class. The runtime invariant the manifest grammar encodes is empirically the same as what the runtime enforces. No action required.

<!-- Append new entries above this line. Keep format consistent. -->
