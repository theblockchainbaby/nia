# Formal Methods Outreach: Cold Email Template

Second wave template, written 2026-06-12 after incorporating Chlipala's feedback ("hard to extract legible evidence of qualifications") and Toby Murray's warm engagement.

Differences from the first wave:
- Honest about what the runtime enforces today versus what Phase I is for
- Cites Toby Murray as warm-engaged, not as committed (do not overclaim)
- Names the production deployment as concrete evidence the substrate exists
- Frames the prover choice as a question for the recipient, not a pre-decided answer
- Offers email-first engagement, with a call as an option, not a requirement
- Closes with a much smaller ask than "join my team"

---

## Template

> **Subject:** Mechanizing a capability containment proof in a one year Phase I (NSF SBIR)
>
> Dr. [LASTNAME],
>
> [ONE TO TWO SENTENCE PERSONALIZED HOOK: cite a specific paper, system, or recent talk of theirs and explain in plain terms how it maps onto the proof obligation I am trying to discharge. Examples below.]
>
> I am York Sims, founder of Caipher AI. Nia is a small open source Python runtime (github.com/theblockchainbaby/nia, AGPL, around 2,400 lines) that confines an LLM augmented worker to actions declared in a YAML manifest. **What it enforces today is a static, dynamically checked action list.** What it does not enforce yet, and what Phase I is for: a deny by default capability model, a mediated judgment step that the model can only invoke through a declared condition, and a mechanized proof that the executor cannot circumvent either.
>
> Phase I deliverables, as I have them sketched: formal semantics of the manifest grammar and the executor's dispatch loop; mechanized capability soundness theorem; mechanized condition gating completeness theorem; a small case study against a real worker. I am weighing Coq, Lean, and a lighter model checked route for a one year scope. The tradeoff is squarely your territory and I would value your read whichever direction you would push.
>
> Two pieces of context that may matter to your decision:
> 1. The runtime is already in production. As of today it has logged 41 unattended successful runs of one worker on a daily cron and 67 unattended runs of another on a twice daily cadence, stderr clean. Substrate exists; the Phase I work lands on the proof, not on plumbing.
> 2. I have a warm initial conversation with [Toby Murray at the University of Melbourne / OTHER NAMED COLLABORATOR if applicable] on the formal methods side. I am still actively assembling the rest of the team.
>
> The NSF Project Pitch (#00115269) is in review now, response expected by 11 July. If invited, the full proposal would name a senior formal methods personnel under a paid Phase I subaward owning the mechanized proof.
>
> Would you be open to a short email exchange to see if it fits? Happy to send the technical brief and a 60 second runtime tour as a starting point.
>
> Thanks,
> York Sims
> Founder, Caipher AI
> yorksims@gmail.com | 918-470-0208
> github.com/theblockchainbaby/nia

---

## Personalization hooks per researcher

These are starter hooks. Tighten the language to the actual relevance.

### Toby Murray (University of Melbourne) — already engaged
*Hook used in original outreach.* Cited the seL4 noninterference proof and the DPhil thesis on object capability program security. Warm conversation underway. Do not re-cold the same researcher.

### Adam Chlipala (MIT) — declined, asked for referral
*Soft no received 2026-06-12.* COI with Nectry pivot and BlueRock Security advisory role. May refer a student or postdoc. Wait for response on referral ask.

### Lean / Mathlib (e.g. Leonardo de Moura, Mario Carneiro, Sebastian Ullrich)
*Hook:* "Your work on [Lean 4 / mathlib / specific theorem prover infrastructure] is the kind of substrate I am evaluating for a one year mechanization. I am specifically weighing whether the proof obligation below is better expressed in Lean's dependent types or in Isabelle/HOL's classical logic with the seL4 ecosystem in reach, and I would value your read."

### Coq / Rocq community
*Hook:* "Your work on [specific Coq library, system, or paper] is the closest precedent I have found for the kind of small runtime mechanization I am trying to discharge in a one year window. I would value your read on whether the proof obligation below is tractable in Coq/Rocq at that scope."

### TLA+ / model checked route (e.g. Leslie Lamport, Markus Kuppe)
*Hook:* "Your work on [specific TLA+ system, paper, or industrial deployment] is the kind of evidence I am leaning on to weigh model checking against interactive proof for this scope. The runtime I am trying to verify is small enough that a TLA+ model of the executor might be the right shape; I would value your read."

### Object capability researchers (e.g. Alan Karp, Mark Miller, Sergio Maffeis)
*Hook:* "Your work on [E, Caja, capability calculus] is the foundational shape I am trying to discharge for a runtime that admits a language model into the control loop. I would value your read on whether a mediated judgment step preserves the capability soundness property in your sense."

### LLM verification researchers (e.g. people working on formal methods plus LLMs)
*Hook:* "Your recent work on [specific paper] is the closest existing precedent for what I am trying to prove about a runtime that gates an LLM invocation behind a declared condition. The proof shape is below; I would value your read."

---

## Do not include

- Any claim that the runtime today proves what Phase I is meant to prove. Senior researchers will check.
- Any framing that overstates the size or qualifications of the team. State what is true.
- Any reference to "advisor role" or "PI from outside" — under NSF SBIR rules the PI must be primarily employed by the small business. The correct terms are **senior personnel under subaward**, **named formal methods collaborator**, **paid consultant**, or **letter of support author**.

---

*Updated 2026-06-12. Source: outreach correspondence with Toby Murray (warm engagement) and Adam Chlipala (declined with feedback). Tighten further as additional replies come in.*
