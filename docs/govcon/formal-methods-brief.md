---
title: Mapping Nia's capability containment to formal foundations
subtitle: A short brief for Prof. Toby Murray, in advance of our exchange
author: York Sims, Founder, Caipher AI
date: 2026-06-12
---

# What Nia is

Nia is a local Python runtime for automation augmented by LLMs. Workers are declarative: a `worker.yaml` manifest enumerates the actions a worker may perform. The runtime executor refuses to invoke any action not declared in the manifest. Actions come in two kinds. `kind: deterministic` is plain code. `kind: judgment` is the only kind permitted to invoke a language model, and the manifest loader refuses to parse a judgment action that lacks a `condition:` predicate. The predicate is evaluated against the persisted results of prior actions in the same run.

The runtime is roughly 850 lines of Python: a manifest parser, a condition evaluator, an executor, a registry, and a run state store. The implementation is open source (AGPL) and on GitHub at `github.com/theblockchainbaby/nia`. It is small on purpose.

# The central claim, in formal terms

The thesis Nia stakes is that a worker is structurally unable to exceed the capability manifest it was deployed with. Informally: telling an agent "do not send emails" and not giving it a send email action are not the same thing. The first is an instruction the model is free to misread. The second is a fact about the universe the model inhabits.

Stated more carefully: for any manifest $M$ and any run $r$ of a worker under $M$, every action $a$ observed in $r$ satisfies $a \in \mathrm{actions}(M)$. Furthermore, for any judgment action $j$ observed in $r$, the condition predicate $\mathrm{cond}(j)$ evaluated against the persisted results of $r$ is true. These are the two core soundness properties the runtime is meant to enforce. Today they are enforced dynamically by the executor and exercised by a unit test suite. They are not yet mechanized.

The shape of the formal target is intentionally aligned with two strands of your work. The capability soundness property maps to the foundational object capability claim that authority is bounded by held references. The noninterference property between independent workers, were we to extend the formalization there, parallels the integrity component of the seL4 information flow theorem: workers with disjoint capabilities do not interfere with each other.

# Concrete proof obligations

Phase I scope, in priority order:

1. **Capability soundness of the executor.** For all $M$ and all $r$, every dispatched action $a$ is in $\mathrm{actions}(M)$. The statement is small; the proof requires formalizing the executor's dispatch loop and the manifest data structure.
2. **Condition gating completeness for judgment actions.** No judgment action runs unless its condition predicate evaluates true against $\mathrm{results}(r)$. This is the structural constraint that distinguishes Nia from agent frameworks that gate by prompt.
3. **(Phase II stretch) Noninterference between independent workers.** Workers with disjoint capability sets do not interfere on shared run state. The connection to your seL4 noninterference theorem is direct.
4. **(Phase II stretch) Dry run observational equivalence.** Every worker can be executed in a dry run mode where side effects are mocked. The proof obligation is that the dry run trace and the real trace are observationally equivalent modulo a side effect projection. This is essentially a bisimulation claim.

# Where today is, where the proof needs to be

**Today:** Python implementation, dynamically checked invariants, unit tests as the only assurance artifact.

**What is missing:** a formal semantics of the manifest grammar, a formal semantics of the executor's dispatch loop, and mechanized proofs of (1) and (2) in an interactive theorem prover or model checker. The candidate targets I am weighing are Isabelle/HOL (your seL4 ecosystem and the most natural fit), Lean 4, and TLA+ for a more lightweight model checked approach. I would value your read on the right tradeoff for a one year Phase I.

# Phase I deliverables, as currently scoped

1. A formal semantics of the manifest grammar and the executor's dispatch loop in a chosen theorem prover or model checker.
2. A mechanized proof of capability soundness (claim 1 above).
3. A mechanized proof of condition gating completeness (claim 2).
4. A small case study, ideally a real production worker that exercises the formal model, to demonstrate the approach scales beyond toy manifests.

# What I am asking of you

In order of decreasing commitment, any of which is a useful answer to the question NSF is asking, which is whether the formal claim has a credible expert behind it:

1. **Joint Principal Investigator or senior advisor** on the Phase I. NSF SBIR rules make a subaward based in Melbourne awkward; happy to find a structure that works on your side.
2. **Named formal methods consultant,** with a letter of support for the full proposal package.
3. **Informal advisor** whose name I cite as a technical sounding board.
4. **An off the record read** on whether the Phase I scope above is tractable in the time available.

I would rather have the truthful smallest commitment from you than a larger nominal one that does not match reality.

Thank you for the time.

---

**York Sims**
Founder, Caipher AI
yorksims@gmail.com
github.com/theblockchainbaby/nia
