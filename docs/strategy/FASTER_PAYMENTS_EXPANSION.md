# Product Strategy — From Check Review to a Rail-Agnostic Payment Exception Console

> **Audience**: Founders, product, early investors.
> **Thesis**: The Check Review Console's real asset is a reusable pattern —
> *human-in-the-loop exception review + cross-institution intelligence* — that
> generalizes far beyond checks. The strategic move is to evolve it into a
> **rail-agnostic Payment Exception Review Console** before checks decline
> further.
> **Last updated**: 2026-06

---

## 1. Why expand

Checks are a structurally shrinking rail (~7%/yr fewer in the US), even as
per-item check fraud *losses* rise (check washing/alteration). Meanwhile payment
**volume and fraud are migrating to faster rails** — FedNow, RTP, Zelle, wires —
where settlement is instant and irreversible, so a fast, well-audited human
review step is worth even more than it is for checks.

A tool tied only to checks has a shrinking TAM. The same console applied across
rails has a growing one — and reuses ~80% of what already exists here:

| Existing capability (already built) | Reused by faster-payments console |
|---|---|
| Prioritized review queue + SLA tracking | ✅ unchanged |
| Context panel (account tenure, balance, velocity) | ✅ unchanged |
| Configurable, explainable detection rules | ✅ retargeted to payment fields |
| Dual control + threshold routing | ✅ unchanged |
| Immutable, hash-chained audit trail + evidence sealing | ✅ unchanged |
| Multi-tenant isolation + RBAC | ✅ unchanged |
| Cross-bank network intelligence | ✅ higher value (instant rails) |

The check viewer is the main check-specific piece; everything else is a
payments-exception platform that happens to currently show check images.

---

## 2. Sequencing (wedge → expand → defend)

1. **Win the check wedge.** Land 3–5 design-partner banks, ship one real core
   integration, complete SOC 2 Type II. This earns the reference base and the
   right to charge.
2. **Expand the same console to faster payments.** Add rail-specific intake and
   field models (below) while reusing queue/context/dual-control/audit. Sell as
   an add-on rail to existing customers first (land-and-expand), then as the
   lead product to new logos.
3. **Defend with the network.** As participating banks accumulate, the
   cross-institution fraud signal becomes the moat. Monetize it last, once it is
   dense enough to generate hits in normal operation.

---

## 3. Adjacent products, ranked

Ranked by TAM × fit-with-current-platform × defensibility.

1. **Faster-payments fraud review (FedNow / RTP / Zelle / wire)** — *build next.*
   Biggest and growing TAM; future-proofs the company; ~80% platform reuse.
   Irreversible settlement makes the human-in-the-loop step high-value.
2. **Reg E dispute & chargeback case management** — large, growing ops burden
   under heavy examiner scrutiny; incumbent tooling is poor. Natural fit with the
   existing case/audit/dual-control engine.
3. **Positive Pay / Payee Positive Pay modernization** — hated legacy UX, sticky
   revenue, direct extension of check review; easy cross-sell to the same buyer.
4. **Deposit / new-account & synthetic-identity fraud at onboarding** — front-of-
   funnel fraud; pairs naturally with the network signal.
5. **Check-washing / alteration image forensics (ML)** — upgrade detection from
   rules to a model; addresses the #1 rising check-loss vector and justifies
   premium pricing. (Also hardens the existing check product.)
6. **BSA/AML alert triage + SAR-narrative co-pilot** — big budgets but crowded
   (Verafin/Nasdaq). Enter only via the network-data angle, not head-on.
7. **Consortium fraud network as a standalone data product** — highest-moat,
   longest horizon; requires scale and competes with Early Warning / Advanced
   Fraud Solutions (TrueChecks). Earn it through the workflow products first.

---

## 4. What a faster-payments rail needs (delta from checks)

A new rail is mostly a new **intake adapter** + **field/context model** +
**rule pack**; the workflow, audit, RBAC, and network plumbing are shared.

- **Intake adapter** per rail. Unlike check images (pulled on demand), faster-
  payment alerts arrive as **real-time messages** (ISO 20022 pacs/pain for
  FedNow/RTP, proprietary feeds for Zelle, wire/Fedwire messages). Add a
  streaming/webhook intake alongside the existing pull/SFTP connectors.
- **Field model** per rail: debtor/creditor, amount, settlement timestamp,
  originator/beneficiary FI, remittance info, channel — replacing MICR/payee/
  signature. The account-context panel is reused as-is.
- **Decision actions** shift from pay/return/hold to **hold / release / reject /
  recall-request** within the rail's (very short) decision window. SLA tracking
  becomes mission-critical because windows are seconds-to-minutes, not hours.
- **Rule pack** retargeted to instant-payment fraud patterns: first-time payee,
  account-takeover velocity, mule-account indicators, amount anomalies, scam/APP
  (authorized push payment) signals.
- **Network indicators** retargeted from `payee_hash` to beneficiary/originator
  hashes and device/behavioral markers — the same anonymized-signature pattern
  already implemented for checks.

---

## 5. Risks & watch-items
- **Decision-window pressure.** Instant rails demand sub-minute review or
  automated hold-then-review. The current SLA model assumes hours; the
  faster-payments mode needs near-real-time queueing and possibly auto-hold.
- **Integration surface.** Real-time intake is a bigger lift than file/SFTP and
  varies per rail and core/processor; scope one rail end-to-end before fanning
  out.
- **Crowded fraud-platform incumbents** at the high end (Verafin, etc.). Win on
  community-bank fit, explainability, and the cross-bank network — not on
  breadth.

---

*Strategy document — directional, not a committed roadmap. Validate rail
priority with design-partner banks before building.*
