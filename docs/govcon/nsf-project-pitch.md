# NSF SBIR Project Pitch — Nia (Caipher AI, LLC) — FINAL

*Sharpened + adversarially reviewed 2026-06-11. Code claims verified against the actual repo (permissions parsed but not enforced; no LLM mediation step yet; impls are arbitrary Python). Char counts confirmed under NSF limits.*

---

## 1. The Technology Innovation  (Q13)  (~2,990 / 3,500)

Whether runtime-enforced capability constraints can deliver verifiable, generalizable safety for LLM-driven agents without destroying the flexibility that makes them useful is unsolved, may not be solvable in the form we propose, and that uncertainty is the research.

Autonomous agents today are governed at the prompt layer. An operator writes "do not send email" or "never touch production" and trusts the model to obey. Under adversarial pressure, prompt injection, or simple misreading, a capable model can ignore the instruction and act anyway. The guarantee is requested of the model, not enforced by the system, so it is probabilistic at best and absent under attack. No prompt engineering converts a request into a guarantee.

Nia proposes to move the guarantee from the prompt layer to the runtime layer: an agent's permitted capabilities are declared in a manifest, the LLM is invoked only at gated judgment steps, and any action outside the manifest is structurally unreachable. The categorical difference from guardrail prompts, output classifiers, and human review is that those inspect model behavior after the fact, whereas a capability manifest is meant to make out-of-scope actions nonexistent to the agent. The approach originated in operating LLM agents in production, where instructing an agent not to take an action repeatedly proved to be no guarantee that it would not.

The high-risk claim is that "structurally unreachable" can be made true and proven. A working open-source prototype (github.com/theblockchainbaby/nia, AGPL-3.0, Python) is our experimental apparatus, not evidence the question is answered. It demonstrates the deterministic-versus-judgment execution split and dry-run preview, but it enforces only a static author-declared action list; it does not yet enforce a deny-by-default permission model, the mediated LLM judgment step does not yet exist, and impls are ordinary Python that can import anything. Building and proving those three pieces is the Phase I research, and three things could defeat it.

First, mediating a Turing-complete implementation is a confinement problem: a capability check is meaningless if the function behind it can reach a side effect directly, so the trusted computing base and a sandboxing boundary must be defined, and may not hold. Second, capability-level enforcement may not imply behavior-level safety, because an LLM invited into the judgment loop can compose permitted actions, or choose their arguments, to reach an unintended harmful outcome; this is information-flow security against an adversary we deliberately admit. Third, a guarantee that depends on one execution model may be irreducibly framework-specific rather than foundational.

If it succeeds, "this agent cannot exceed its declared capabilities, even under a manipulated prompt" becomes a property the runtime enforces and an auditor can verify. Showing precisely where it fails is an equally real contribution to AI assurance and trusted autonomy.

---

## 2. The Technical Objectives and Challenges  (3,281 / 3,500)

Phase I must produce a formal containment model with an explicit trusted computing base, a stated theorem of what runtime enforcement can and cannot guarantee, a falsifiable measurement of the safety-versus-utility frontier, and evidence on whether containment is framework-portable. Each objective is built so a negative result is informative, not a failure.

Objective 1: Formalize the manifest and prove containment, with the boundary stated honestly. We model the runtime as a small-step operational semantics, define a capability as a typed effect, and state the containment theorem: every side-effect-producing transition is justified by a capability in the manifest, proven by induction over the reduction relation for a core calculus. Challenge: the real Python runtime is not the calculus. Impls can import anything, so the interpreter, importlib, and each impl's transitive imports are inside or outside the trusted computing base, and we must say which. Approach: define the TCB explicitly, build a reference monitor that mediates impl dispatch, sandbox the impl boundary, and characterize the soundness gap between proof and implementation. The honest risk is that a Turing-complete impl cannot be contained without sacrificing what makes builtins useful.

Objective 2: Build and bound a verification layer over the planned action graph. We check the action sequence against the manifest statically on the plan and dynamically at each step before any side effect fires. Challenge: today the action set is static and trivially decidable; undecidability appears only once an LLM picks actions and arguments at runtime. Approach: state precisely what is statically decidable (the declared action set) versus what is not (argument-level and data-flow properties under model choice), and verify the decidable fragment while bounding the rest with a runtime gate.

Objective 3: Test whether a framework-agnostic containment invariant exists at all. The research question is whether a minimal semantic interface preserves containment independent of a framework's planning and execution model. We build the mediated judgment step Nia lacks today, then attempt to attach the same invariant at the tool-dispatch boundary of LangChain, the function-calling boundary of the OpenAI Assistants API, and MCP tool invocation. Challenge: some frameworks have in-process tool calls over shared memory with no single mediating chokepoint, where containment may be impossible. Approach: locate the interception point in each, port two, and document where the invariant breaks. The headline negative result is that containment is an artifact of one execution model.

Objective 4: Quantify the safety-utility frontier against a falsifiable hypothesis. We hypothesize a usable region exists where zero out-of-manifest side effects succeed and task completion stays within a defined margin of an ungoverned baseline. Approach: assemble a benchmark of agent tasks indexed by open-endedness and required capability breadth, sweep manifest tightness, measure utility (task success at fixed budget) and safety (out-of-manifest effects attempted versus blocked), and test whether the region is non-empty and how it scales. Failure is a measured demonstration that no operating point clears the bar.

The sustainable advantage is owning this proven result and the reference implementation auditors adopt, which a competitor cannot fork from open code.

---

## 3. The Market Opportunity  (1,576 / 1,750)

The first customer is a defense or regulated-finance operator who must demonstrate to an auditor that a deployed agent provably cannot exceed its declared capabilities, a requirement that DoD "Runtime Assured Autonomy" and CDAO "Trusted AI and Autonomy" programs already fund and that NIST AI RMF and EU AI Act high-risk provisions push toward enforceable, auditable controls.

The concrete trigger is liability, not hype: when an agent executes an unauthorized financial transaction or an out-of-scope production change, that is a reportable compliance event the operator is accountable for. These buyers cannot accept probabilistic safety. The value is a verifiable guarantee an operator and an auditor can rely on, plus dry-run preview and full audit logs, rather than a prompt they must trust.

Incumbents are prompt-layer guardrails, output classifiers, and observability dashboards that inspect behavior after the model acts. The real threat is the agent frameworks themselves adding native capability gating. That is exactly the non-generalizable, non-auditable outcome Objective 3 argues against: a control built into one framework cannot be the independent assurance layer an auditor trusts. Nia's value is being framework-agnostic and externally verifiable.

The defensible position is not the AGPL core or a governance wrapper, both of which a competitor can fork. It is being the reference implementation that assurance auditors and procurement frameworks standardize on, backed by production operating history (Caipher has run Nia continuously, 24/7, in its own operations) and the Phase I research result, which a fork cannot replicate without redoing the work.

---

## 4. The Company and Team  (1,679 / 1,750)

The founder built the exact open-source system whose research risk this Phase I tests, and reviewers can read it today at github.com/theblockchainbaby/nia, so the team starts from inspectable code rather than a concept. Caipher AI, LLC is a U.S.-owned for-profit small business; York Sims owns 51 percent and will serve as Principal Investigator.

York Sims is a self-taught software engineer with a record of taking systems from an empty repository to production. The directly relevant work is the Nia runtime itself (Python: deterministic executor, manifest parser, dry-run preview), the production deployment running Nia 24/7 in Caipher's own operations, and hands-on LLM integration on the exact surface this research governs (Claude API, the Model Context Protocol, retrieval-augmented generation). That is the engineering core for the executor, reference-monitor, and benchmark work in Objectives 2, 3, and 4, which the PI can credibly execute and lead with empirical, adversarial, and measurement-based methods.

The honest gap is deep formal-verification expertise. The containment proof and the decidability characterization in Objectives 1 and 2 require rigor beyond engineering practice, and they are the part of the proposal the research framing leans on hardest. We will close this with a named subaward to a formal-methods researcher who owns the operational semantics, the containment theorem, and the trusted-computing-base characterization, with Phase I budget allocated for it; full formal proof is scoped as advisor-owned, while the PI leads the empirical and adversarial objectives. We will recruit this collaborator from an academic formal-methods group and name them before award.
