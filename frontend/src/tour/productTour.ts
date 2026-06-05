import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

const DONE_KEY = 'cr_product_tour_v1_done';

// Steps target elements by [data-tour="..."]; popover-only steps (no element)
// render as centered cards. Steps whose target isn't on the page are skipped so
// the tour stays robust across roles/screens.

// The dashboard tour is the "overview" tour (also used for first-visit auto-start).
const DASHBOARD_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Welcome to Check Review Console',
      description:
        "A quick tour of how an item flows from intake to a cryptographically-sealed, audited decision. Use the arrows or Esc to exit anytime. Tip: re-run this tour on any page for guidance specific to that screen.",
    },
  },
  {
    element: '[data-tour="bank-volume"]',
    popover: {
      title: 'Bank-scale context',
      description:
        '~10,000 items are presented each day; ~97% clear straight through. The review queue (~267 items) is the small exception slice — that gap is the automation opportunity.',
      side: 'bottom',
    },
  },
  {
    element: '[data-tour="dashboard-kpis"]',
    popover: {
      title: 'Operational at-a-glance',
      description:
        'Pending volume, items processed today, SLA breaches and the dual-control backlog — live from the queue.',
      side: 'bottom',
    },
  },
  {
    element: '[data-tour="risk-distribution"]',
    popover: {
      title: 'Portfolio risk mix',
      description: 'The risk breakdown of the open queue — click any segment to filter straight to those items.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="nav-Review-Queue"]',
    popover: {
      title: 'Your work list',
      description: 'The Review Queue is where you triage and action exception items. Let’s look at the rest of the platform from the nav.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="nav-Automation"]',
    popover: {
      title: 'Decision automation (STP)',
      description:
        'Auto-clear low-risk items and route only exceptions to people. Tune the policy, validate in shadow mode, spot-check with QA, and see the projected annual value.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="start-reviewing"]',
    popover: {
      title: 'Jump in',
      description: 'Open a check, review the image and detected flags, then record a decision. That’s the loop. Enjoy the demo!',
      side: 'top',
    },
  },
];

// Descriptive, page-specific tours. These use popover-only steps so they are
// robust regardless of which cards a given role can see.
const QUEUE_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'The review queue',
      description:
        'Your work list — the daily exception slice routed out of straight-through processing. Everything here needs a human decision.',
    },
  },
  {
    popover: {
      title: 'Triage & sort',
      description:
        'Filter by Pending, SLA-breached, Dual-control or Processed, and sort by risk, amount or SLA so the most urgent items surface first.',
    },
  },
  {
    popover: {
      title: 'Claim work safely',
      description:
        '“Pull next item” claims the top item for you. Soft locks prevent two people from working the same check at once.',
    },
  },
];

const REVIEW_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Reviewing a check',
      description:
        'Everything you need to decide one item: the cheque image, account context, history, network intelligence and the decision panel.',
    },
  },
  {
    popover: {
      title: 'Image viewer',
      description:
        'Zoom, pan and magnify the image; toggle ROI overlays (amount box, signature, MICR). Shortcuts: + / − zoom, f fit, m magnifier, r ROI, Tab front/back.',
    },
  },
  {
    popover: {
      title: 'Item Context — now resizable',
      description:
        'Account tenure, balances and behaviour that drive the flags. Drag the handle on its right edge to widen or narrow the panel; the rest of the layout reflows to fit.',
    },
  },
  {
    popover: {
      title: 'Review recommendation',
      description:
        'Record approve / return / reject / escalate with reason codes and notes. High-value items route to a second approver (dual control). The decision is sealed into the evidence chain.',
    },
  },
];

const APPROVALS_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Two-person dual control',
      description:
        'High-value or policy-flagged items wait here for a second approver. A reviewer can never approve their own recommendation — enforced server-side.',
    },
  },
  {
    popover: {
      title: 'Approve or send back',
      description:
        'Confirm the recommendation or return it to the reviewer with a reason. Every action is audited and added to the item’s sealed evidence trail.',
    },
  },
];

const REPORTS_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Reports',
      description:
        'Operational and governance reporting, consistent with the dashboard: ~10k presented/day, ~97% straight-through, the rest reviewed by people.',
    },
  },
  {
    popover: {
      title: 'Throughput & decisions',
      description:
        'Daily presented vs. processed volume, the approve/return/reject breakdown and approval rate over your chosen window.',
    },
  },
  {
    popover: {
      title: 'Reviewer performance & exports',
      description:
        'Per-reviewer decision activity, plus CSV and audit-ready PDF exports (daily activity, daily summary, executive overview).',
    },
  },
];

const AUTOMATION_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Decision automation (STP)',
      description:
        'Model auto-clearing low-risk items straight through while routing exceptions to people. Adjust the risk tier and amount cap to set your appetite.',
    },
  },
  {
    popover: {
      title: 'Shadow mode & guardrails',
      description:
        'The policy is scored against what reviewers actually decided, so you can see accuracy and any misses before turning anything on. Guardrails always keep dual-control items with a person.',
    },
  },
  {
    popover: {
      title: 'QA spot-check & ROI',
      description:
        'A governance sample of would-be auto-cleared items is checked against the human outcome to give a pass rate, alongside the projected annual value (labour and FTEs freed).',
    },
  },
];

const OPERATIONS_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Platform & integrations',
      description:
        'The operational backbone: core connectors (image intake, decision commit, account context), evidence-chain verification, audit drill-down and security.',
    },
  },
  {
    popover: {
      title: 'Connectors',
      description:
        'Image Intake (A), Decision Commit (B) and Account Context (C) connect the console to the bank’s core and image archive.',
    },
  },
  {
    popover: {
      title: 'Evidence, audit & security',
      description:
        'Verify the cryptographic evidence chain, drill into the immutable audit trail, and track security incidents — all from here.',
    },
  },
];

const ADMIN_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Administration',
      description:
        'Manage users and roles, configure queues, and author the policies and rules that route and gate items.',
    },
  },
  {
    popover: {
      title: 'Policies & rules',
      description:
        'Versioned, tenant-scoped policies. Add, edit or remove rules (conditions and actions); activating a change creates a new auditable version.',
    },
  },
];

const FRAUD_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Fraud intelligence',
      description:
        'Trends and network signals across the institution. Indicators are privacy-preserving (hashed with a server-side pepper) and only surface above a minimum cohort size.',
    },
  },
];

const ARCHIVE_STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Archive',
      description:
        'Search and retrieve decided items and their sealed evidence within the retention window — the system of record for completed reviews.',
    },
  },
];

// Ordered most-specific-first so /review and /fraud match before the catch-all.
const ROUTE_TOURS: { prefix: string; steps: DriveStep[] }[] = [
  { prefix: '/review', steps: REVIEW_STEPS },
  { prefix: '/queue', steps: QUEUE_STEPS },
  { prefix: '/approvals', steps: APPROVALS_STEPS },
  { prefix: '/reports', steps: REPORTS_STEPS },
  { prefix: '/automation', steps: AUTOMATION_STEPS },
  { prefix: '/operations', steps: OPERATIONS_STEPS },
  { prefix: '/connectors', steps: OPERATIONS_STEPS },
  { prefix: '/audit', steps: OPERATIONS_STEPS },
  { prefix: '/security', steps: OPERATIONS_STEPS },
  { prefix: '/admin', steps: ADMIN_STEPS },
  { prefix: '/fraud', steps: FRAUD_STEPS },
  { prefix: '/archive', steps: ARCHIVE_STEPS },
  { prefix: '/dashboard', steps: DASHBOARD_STEPS },
];

function stepsForPath(pathname?: string): DriveStep[] {
  const path = pathname || (typeof window !== 'undefined' ? window.location.pathname : '/dashboard');
  const match = ROUTE_TOURS.find((r) => path.startsWith(r.prefix));
  return match ? match.steps : DASHBOARD_STEPS;
}

function buildDriver(pathname?: string) {
  const steps = stepsForPath(pathname).filter(
    (s) => !s.element || document.querySelector(s.element as string),
  );
  return driver({
    showProgress: true,
    allowClose: true,
    overlayOpacity: 0.6,
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
    steps,
    onDestroyed: () => {
      try {
        localStorage.setItem(DONE_KEY, '1');
      } catch {
        /* ignore */
      }
    },
  });
}

/**
 * Start the guided tour on demand (e.g. from the "Take a tour" button), showing
 * steps specific to the page the user is currently on.
 */
export function startProductTour(pathname?: string) {
  buildDriver(pathname).drive();
}

/**
 * Auto-start the overview tour once per browser (forced on first demo visit),
 * then leave it available via the header button. Call after the dashboard has
 * rendered.
 */
export function maybeAutoStartTour() {
  let done = false;
  try {
    done = localStorage.getItem(DONE_KEY) === '1';
  } catch {
    /* ignore */
  }
  if (done) return;
  // Defer so target elements are mounted/painted.
  setTimeout(() => startProductTour('/dashboard'), 700);
}
