# GovCon Status

A living status document for the NSF SBIR Phase I pursuit. Last updated 2026-06-12.

## Pursuit

NSF SBIR Phase I, AI topic. Framing: AI agent safety and trusted autonomy through runtime capability containment. Up to $305K, no past performance requirement.

## Pitch

- **Status:** SUBMITTED, locked
- **Number:** 00115269
- **Submitted:** 2026-06-11
- **Expected response window:** ~2026-07-11
- **Fallback if silent by 11 July:** email sbir@nsf.gov with the pitch number
- **Final text:** [`nsf-project-pitch.md`](./nsf-project-pitch.md)

## Federal registrations (all 2026-06-11)

| Item | Status |
|---|---|
| UEI | W3KGRQBPAJK5 |
| SAM.gov | Submitted, validating, expected Active late June |
| SBC Control ID | SBC_002678068 |
| ORCID iD | 0009-0005-3258-7517 |
| NSF ID (Research.gov) | 0000A8VZH (org link waits on SAM) |
| EIN | 41-3241116 |
| NAICS | 541511 / 541512 / 541519 / 541715 |

**Watch:** SAM.gov Active notification, late June. When Active, grab CAGE code, finish Research.gov org link, flip site status from Submitted to Active.

**Unconfirmed:** State of formation on the Articles of Organization. Do not assume.

## Production deployment (as of 2026-06-12)

Nia is currently running 24/7 in production on the founder's daily workstation under launchd. Two scheduled workers:

| Worker | Cron | Successful runs | Most recent | Stderr bytes |
|---|---|---|---|---|
| `morning-ops` | `0 3 * * *` (daily 3 AM) | 41 | 2026-06-12 03:05 PDT, 4✓ actions, 132s | 0 |
| `notion-sync` | `0 6,18 * * *` (twice daily) | 67 | 2026-06-12 18:00 PDT, 3✓ actions, 71s | 0 |

Both jobs visible in `launchctl list` as `com.nia.morningops` and `com.nia.notionsync`. Run history surfaced via `nia logs <worker>`. Audit primitives (`nia inspect`, `nia logs`, `nia dry-run`) functional. **The "Nia runs 24/7 in production" claim previously held back for the full proposal is empirically true and demonstrable from terminal in 60 seconds.**

## Formal methods outreach

10 senior researchers contacted in the initial wave. Results so far:

| Name | Institution | Status | Notes |
|---|---|---|---|
| Toby Murray | University of Melbourne | Warm | Reply 2026-06-11: "interested in finding out more." Substantive technical reply sent. Awaiting next message. Strongest current candidate. |
| Adam Chlipala | MIT CSAIL | Declined (soft) | Reply 2026-06-12: scheduling + COI (Nectry pivot + BlueRock Security advisory). Asked for student/postdoc referral. |
| 8 others | TBD | Silent | Second wave with tightened cold email template forthcoming. |

**Held back for the full proposal** (if invited):

- Named formal methods senior personnel under subaward (Toby or successor)
- Letter of support from the same
- Mechanized capability soundness theorem deliverable plan
- Mechanized condition gating completeness theorem deliverable plan
- Prover choice rationale (Coq vs Lean vs TLA+)

## Documents in this folder

| File | Purpose |
|---|---|
| [`nsf-project-pitch.md`](./nsf-project-pitch.md) | The locked pitch text submitted to NSF. |
| [`formal-methods-brief.md`](./formal-methods-brief.md) | One to two page brief mapping Nia's containment claim onto formal foundations. Sent to engaged collaborators after the cold email. |
| [`runtime-tour.md`](./runtime-tour.md) | Six command, sixty second tour of the runtime, with the hello-world manifest in full. |
| [`team-narrative.md`](./team-narrative.md) | The "why this team, why this vehicle, why not from scratch" answer, written after Chlipala's feedback. For the full proposal and for sustained outreach. |
| [`cold-email-template.md`](./cold-email-template.md) | Second wave cold email template, tightened after Chlipala's feedback and Toby's warm engagement. Per-recipient personalization hooks below the template. |
| [`status.md`](./status.md) | This document. Update as state changes. |

## Strategic framing

- **SBIR is the path.** 8(a) is deferred (much harder in 2026, needs a social disadvantage narrative not yet written). Minority owned is a contracting lever, not a grant one.
- **Jobs stay the income engine.** GovCon is a 6 to 18 month build with no near term cash.
- **The pitch was framed honestly.** AI agent safety and trusted autonomy. The runtime today enforces a static action list. The deny by default capability model, mediated judgment step, and mechanized containment proof are the Phase I research. Do not let downstream materials drift from this framing.

## Open items being tracked

1. SAM.gov Active notification (late June)
2. NSF response on pitch #00115269 (~2026-07-11)
3. Toby Murray's next message
4. Chlipala's possible student/postdoc referral
5. Confirm state of formation on the Articles of Organization
6. Second wave cold email to the 8 silent researchers (after one week without reply)
7. If NSF invites: full proposal writing (named collaborator, letter of support, Phase I deliverable plan)
