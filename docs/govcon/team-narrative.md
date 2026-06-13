# Team Narrative

A draft response to the question every formal methods reviewer will ask: *why this team, why this vehicle, why not start a separate venture from scratch.* Written for the NSF SBIR Phase I full proposal and for cold outreach to senior collaborators.

## Why this vehicle and not a from-scratch venture

A senior researcher considering this project as their own from-scratch venture would face a known set of fixed costs before any proof work could begin:

1. **Federal registration substrate.** UEI, SAM.gov registration, SBC Control ID, EIN, NAICS classification, ORCID, and Research.gov account linkage. All complete for Caipher AI as of 2026-06-11. SAM activates late June. Restarting this on a new venture costs 6 to 10 weeks.
2. **A working runtime in production.** Nia v0.1 is open source, AGPL, on GitHub at `github.com/theblockchainbaby/nia`. It implements the deterministic versus judgment execution split, a manifest grammar, an executor, a condition evaluator, a registry, a run state store, a CLI with `inspect`, `dry-run`, `run`, and `logs` audit surfaces, and a macOS adapter. As of 2026-06-12 the runtime is deployed under launchd on the founder's daily workstation and has logged 41 successful unattended `morning-ops` runs and 67 successful unattended `notion-sync` runs across roughly six weeks of continuous operation. Stderr is empty across that window. Restarting this in a new venture costs another three to four months of engineering before the proof work has anything to operate over.
3. **A submitted NSF Project Pitch in queue.** Pitch number 00115269, AI topic, submitted 2026-06-11, response window through 2026-07-11. The thesis already aligns with NSF's AI assurance and trusted autonomy framing. A from-scratch venture would have to wait for the next solicitation cycle and start the pitch process over.
4. **Outreach to credentialed formal methods researchers underway.** Initial substantive replies received from at least one senior researcher (University of Melbourne, Toby Murray) whose published work on the seL4 noninterference proof and on object capability program security maps directly onto Nia's containment claim. Additional outreach to Coq and Lean specialists in progress.

A senior researcher who joins Caipher under a paid Phase I subaward lands directly on the proof obligations. The substrate is already paid for, the runtime already exists, the venture already has a federal review window open, and the technical thesis already has positive expert engagement.

## Why this principal investigator

York Sims is the founder, principal investigator, and at present the sole engineer on the Caipher AI runtime. The relevant credentials are not academic; they are operational.

- **Solo authored, production deployed runtime.** Nia is approximately 2,400 lines of Python plus YAML manifests, two runtime dependencies, AGPL licensed. Manifest grammar, executor, condition evaluator, audit surface, and macOS adapter were designed and built by York. The same individual operates the production deployment. The Phase I work plan includes mechanizing the executor's invariants in an interactive theorem prover and standing up CI alongside the formal model.
- **Adjacent production work.** Aegis Core, a separate open source project at `github.com/theblockchainbaby/aegis-core`, is a 14-service local-first runtime with 230+ passing tests and a public dogfood observation log demonstrating disciplined evidence-driven engineering practice. The aegis-core repo is the public record of how York operates: small surface area, observation before fix, restraint as a feature.
- **Honest scope discipline.** Both the Nia README and York's outreach correspondence with senior researchers explicitly state what the runtime does today (a static, author declared action list enforced dynamically by the executor) and what the runtime does not yet do (deny by default capability model, mediated judgment step, mechanized containment proof). The gap is named, not papered over. That gap is the Phase I research scope, and it is owned by the formal methods collaborator who joins.

## The team shape under Phase I

The Phase I team is two roles:

1. **Principal Investigator (Caipher AI):** York Sims. Owns the runtime, the manifest grammar evolution, the deny by default extensions, the case study worker, the production deployment, and the integration of the formal model back into the running system.
2. **Senior formal methods personnel (subaward):** Owns the formal semantics of the manifest grammar and the executor's dispatch loop, the mechanized capability soundness theorem, the mechanized condition gating completeness theorem, and prover choice (Coq, Lean, or TLA+).

This is a small team by design. Phase I is feasibility, not scale. The narrowness is the point: two principals can land a mechanized proof of a small runtime on a one year clock, where a larger team would be slower and would dilute the assurance argument with collaboration overhead.

## Why the expected outcome is not better served by a from-scratch venture

A formal methods researcher leading their own venture would, after the registrations and runtime work are done, arrive at substantially the same Phase I deliverables: a manifest grammar, an executor, mechanized capability soundness, mechanized condition gating. The substrate Caipher already provides eliminates 4 to 6 months of work that is not on the critical path of the proof. The researcher who joins Caipher at this stage trades equity participation for time to the proof.

That trade is the proposal.

---

*Updated 2026-06-12. Source: production runtime logs, NSF Project Pitch submission, federal registration receipts, outreach correspondence.*
