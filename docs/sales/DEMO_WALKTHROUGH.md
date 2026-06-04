# Check Review Console — Demo Walkthrough (Presenter Script)

A ~15-minute, click-by-click script for demoing the Check Review Console to a
community/regional bank (the demo data is modeled on a ~$2B-asset institution).
Anyone can run this top to bottom. Timings are approximate.

> **Setup:** Sign in as `system_admin_demo` / `DemoSysAdmin123!` (full access).
> Other roles to show RBAC: `reviewer_demo`, `senior_reviewer_demo`,
> `supervisor_demo`, `auditor_demo` (passwords in the README).
> Tip: the in-app product tour (the **"Take a tour"** button, top-right) mirrors
> this flow and auto-highlights each screen.

---

## 0. The story in one line

> "Your team drowns in check exceptions. We auto-clear the obvious-good, route
> only the real exceptions to people, prove it's safe before you turn it on, and
> give you an audit trail examiners love — and here's exactly what it's worth."

Keep coming back to three numbers: **straight-through rate**, **shadow
accuracy**, and **estimated annual value**.

---

## 1. Dashboard — bank-scale context (2 min)

Land on **Dashboard**.

- **"Today across the bank"** strip: *"A bank this size presents ~8–10k items a
  day. ~97% clear straight through automatically. Only a couple hundred — the
  exception slice — land in the human review queue below. Everything we're about
  to show operates on that slice."*
- **KPI tiles:** pending volume, processed today, SLA breaches, dual-control
  backlog — all live.
- **Risk Distribution:** *"The queue itself is mostly low/medium risk — routine
  holds — with high/critical a minority. Click any segment to filter straight to
  those items."*

**Point:** the queue is small and mostly routine — which is exactly why
automation pays off.

---

## 2. Review Queue — triage at volume (2 min)

Go to **Review Queue**.

- Tabs: **Pending / SLA-breached / Dual-control / Processed**, each with live
  counts. Risk-filter chips and sort by **priority / amount / SLA**.
- **Pull next item** (top-right): *"Instead of cherry-picking, a reviewer clicks
  Pull next and gets the highest-priority unclaimed item."* Click it → you land
  on the review screen for that item.
- Back in the queue, point at a row badged **"In use by <reviewer>"**: *"Soft
  locks mean two reviewers never collide on the same check at team scale."*

**Point:** built for a team, not a single user.

---

## 3. Review a check — the core loop (2 min)

From a pending item (or the one you just pulled):

- Walk the **check image** + **account context** (tenure, balances, behavior).
- **AI-detected flags are advisory** — they inform risk, a person decides.
- Record a decision (approve / return / reject) with a reason code.
- Note the **dual-control** path: high-value items need a second approver — a
  reviewer can't approve their own recommendation (show **Approvals**).

**Point:** fast, evidence-based decisions with two-person control where it
matters.

---

## 4. Decision Automation — the headline (4 min)

Go to **Automation**. This is the value story.

1. **Headline tiles:** straight-through rate, shadow accuracy, estimated annual
   value (links to the ROI breakdown on Reports).
2. **Mode:** Off → **Shadow** → Active. *"You never flip a switch blind. Shadow
   mode runs the policy silently and scores it against what your reviewers
   actually decided."*
3. **Auto-clear policy:** drag the **amount cap** / toggle the **risk tier** and
   watch the straight-through rate and disposition donut move live. Guardrails
   (dual control, over-cap, above-tier) always route to a person.
4. **Shadow validation:** *"On the items it would auto-clear, it agreed with
   your reviewers X% of the time, with N would-be exceptions — and it correctly
   kept the real exceptions with people."*
5. **QA spot-check:** scroll to the **Quality Assurance** table. *"Here's the
   ongoing control: a sample of auto-cleared items checked against the reviewer's
   actual decision, with a running QA pass rate. This is your governance answer
   for risk and compliance."*

**Point:** automation you can prove is safe — before and after go-live.

---

## 5. Reports — what it's worth (2 min)

Go to **Reports** → **Automation value** panel.

- The assumptions are editable (annual volume, handle time, loaded cost, fraud
  prevented). *"Plug in your numbers."*
- Read the headline: **estimated annual value**, **labor saved**, **reviewer
  capacity freed (FTEs)**, **fraud prevented** — all driven by the live
  straight-through rate.
- Mention the rest of Reports: throughput, decision breakdown, reviewer
  performance, and one-click **PDF exports** (daily summary, executive overview).

**Point:** a CFO-ready number that moves when you change the policy.

---

## 6. Trust & operations (2 min)

Quick hits to close the credibility gap:

- **Fraud Trends:** cross-bank fraud network intelligence (opt-in, no PII).
- **Operations hub:** core connectors (image intake, decision commit, account
  context), **cryptographic evidence-chain verification**, audit drill-down,
  security incidents.
- **Archive & Audit:** immutable, searchable decision history — examiner-ready.
- **Admin → System Metrics:** health, RBAC, policies, and the **Reseed demo
  data** button (recreates a fresh dataset between demos in ~20s).

**Point:** bank-grade security and auditability, not just a pretty queue.

---

## Closing

> "So: most of your volume never touches a person, you proved the policy agrees
> with your reviewers before turning it on, and that's **$X/year** and **N
> analysts** of capacity back — on top of the fraud you catch and an audit trail
> that makes exams boring. Where would you want to start?"

---

### Cheat sheet — where each feature lives

| Capability | Screen |
| --- | --- |
| Bank-scale daily volume | Dashboard → "Today across the bank" |
| Triage / Pull-next / soft locks | Review Queue |
| Decision + dual control | Review screen / Approvals |
| Straight-through policy, shadow, QA | Automation |
| ROI / value | Reports → Automation value |
| Fraud network | Fraud Trends |
| Connectors, evidence chain, incidents | Operations |
| Immutable history | Archive / Audit |
| Reseed between demos | Admin → System Metrics |

> All figures are a live simulation over synthetic demo data — clearly labeled
> in-app. No real PII.
