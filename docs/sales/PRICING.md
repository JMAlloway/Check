# Check Review Console — Pricing Guide

> **Audience**: Founders, sales, and finance. Internal pricing reference and
> starting point for customer proposals.
> **Status**: v1 framework. Numbers are list/anchor targets, not floors —
> see *Deal Guidance* before quoting.
> **Last updated**: 2026-06

---

## 1. Pricing philosophy

Price on **value delivered**, anchored to the ROI the product creates, not on
seats or per-item volume.

- **Why not per-seat?** A workflow tool priced per reviewer rewards the buyer
  for minimizing seats — the opposite of adoption. Use a platform fee with
  generous seat caps instead.
- **Why not per-item?** Check volume is structurally declining (~7%/yr). Tying
  revenue to a shrinking rail shrinks the contract every year. Anchor to the
  institution (asset tier), which is stable.
- **The ROI anchor.** `SALES_FEATURES_BENEFITS.md` models ~$135k/yr of benefit
  for a $500M-asset bank (reviewer efficiency + fraud-loss reduction + audit
  prep). Value-based SaaS typically captures **10–25%** of delivered value →
  ~$15k–$35k/yr of platform value for that bank, which the tiers below reflect.

---

## 2. List pricing (GA target)

Annual subscription, tiered by institution asset size, plus a Network add-on
and a one-time implementation fee.

| Tier (assets)   | Platform / yr | Network Intelligence add-on / yr | One-time implementation |
|-----------------|---------------|----------------------------------|-------------------------|
| **< $500M**     | $24k – $36k   | + $9k                            | $10k – $15k             |
| **$500M – $2B** | $40k – $65k   | + $15k                           | $15k – $25k             |
| **$2B – $10B**  | $75k – $120k  | + $25k – $40k                    | $25k – $40k             |

Included in every tier: all core review/workflow/audit features, standard
support (M–F business hours + 24/7 P1), admin + end-user training, and the
three connectors (image intake, decision commit, account context).

### Add-ons / line items
- **Network Intelligence** — the cross-bank fraud signal. Priced separately
  because it is the differentiator and has near-zero marginal cost with strong
  network effects. **Discount or comp this aggressively for early adopters** to
  build network density (the signal is only worth paying for once N banks
  participate).
- **Multi-charter / holding company** — additional tenants at 50–70% of the
  per-charter platform fee (shared infra, incremental isolation).
- **On-prem / private-cloud deployment** — +20–35% over cloud-hosted; reflects
  support and release-management overhead. Most community banks should take
  cloud-hosted.
- **Source-code escrow, custom training, custom integrations** — quoted
  separately.

---

## 3. Deal guidance — price for *today's* maturity

The list table above is the **GA target once the product has earned it**. As of
this writing the product is pre-GA on several dimensions that bank vendor-risk
teams will probe (see `VENDOR_FAQ.md` items marked `[CUSTOMIZE]`):

- SOC 2 Type II not yet completed.
- Core-banking connectors are wire-format-accurate but not yet proven against a
  live core in production.
- The fraud network is architecturally real but has no live multi-bank density
  yet.
- No production reference customers.

Until those close, **do not quote list.** Sell a *design-partner* program:

- **3–5 design-partner banks** at **~50% off list**, in exchange for being a
  named reference and an integration partner.
- **Paid pilot**: $10k–$15k for a 30–90 day pilot, **credited to year one** on
  conversion. A paid pilot qualifies the buyer and funds the integration work.
- **Comp the Network add-on** for design partners — you need their data in the
  network more than you need their add-on revenue.
- **Lock 2–3 year terms** at the discounted rate so the reference relationship
  outlasts the discount, with a documented step-up to list at renewal.

Raise toward list once you have: SOC 2 Type II + ≥3 live core integrations +
≥3 referenceable banks + a network with enough participants to generate
cross-bank hits in normal operation.

---

## 4. Worked example — $500M-asset community bank

| | Design-partner (now) | GA (post-SOC 2 + references) |
|---|---|---|
| Platform | ~$25k/yr (50% off) | $50k/yr |
| Network add-on | comped | $15k/yr |
| Implementation | $12k (pilot credited) | $20k |
| **Year-1 contract** | **~$25k + pilot** | **~$85k** |
| Modeled annual benefit | $135k | $135k |
| Effective value capture | ~18% | ~48% list / negotiated down |

The design-partner price is deliberately well under the value line to remove
adoption friction and buy references; GA pricing moves capture back toward the
10–25%-of-value band after discounting.

---

## 5. Contract mechanics
- **Term**: annual minimum; 2–3 year preferred (with renewal step-ups).
- **Billing**: annual in advance; implementation invoiced at kickoff.
- **Limitation of liability**: typically capped at 12 months of fees (confirm
  with counsel — see `VENDOR_FAQ.md`).
- **Price protection**: cap annual uplift (e.g., CPI or 5%, whichever is lower)
  for multi-year deals to ease procurement.

---

*This is an internal framework. Final pricing is set per deal based on asset
size, check-exception volume, deployment model, and competitive context.*
