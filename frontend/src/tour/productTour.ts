import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

const DONE_KEY = 'cr_product_tour_v1_done';

// Steps target elements by [data-tour="..."]; popover-only steps (no element)
// render as centered cards. Steps whose target isn't on the page are skipped so
// the tour stays robust across roles/screens.
const STEPS: DriveStep[] = [
  {
    popover: {
      title: 'Welcome to Check Review Console',
      description:
        "A quick tour of how an item flows from intake to a cryptographically-sealed, audited decision. Use the arrows or Esc to exit anytime.",
    },
  },
  {
    element: '[data-tour="nav-Review-Queue"]',
    popover: {
      title: 'The review queue',
      description:
        'Your work list. Triage by Pending, SLA-breached, Dual-control or Processed, sort by risk/amount/SLA, and page through it at volume. Reviewers can also "Pull next item" to claim the top item — soft locks stop two people working the same check.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="nav-Approvals"]',
    popover: {
      title: 'Two-person dual control',
      description:
        'High-value items require a second approver here — a reviewer cannot approve their own recommendation.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="bank-volume"]',
    popover: {
      title: 'Bank-scale context',
      description:
        'Thousands of items are presented each day; the overwhelming majority clear straight through. The review queue you work is the small exception slice — that gap is the automation opportunity.',
      side: 'bottom',
    },
  },
  {
    element: '[data-tour="dashboard-kpis"]',
    popover: {
      title: 'Operational at-a-glance',
      description:
        'Pending volume, items processed today, SLA breaches and the dual-control backlog — live.',
      side: 'bottom',
    },
  },
  {
    element: '[data-tour="risk-distribution"]',
    popover: {
      title: 'Portfolio risk mix',
      description: 'See the risk breakdown of the queue — click any segment to filter straight to those items.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="nav-Automation"]',
    popover: {
      title: 'Decision automation (STP)',
      description:
        'Auto-clear low-risk items straight through and route only the exceptions to people. Tune the policy, validate it in shadow mode against real reviewer decisions, spot-check it with built-in QA, and see the projected annual value (labor + FTEs freed).',
      side: 'right',
    },
  },
  {
    element: '[data-tour="nav-Operations"]',
    popover: {
      title: 'Platform & integrations',
      description:
        'Core connectors (image intake, decision commit, account context), cryptographic evidence-chain verification, audit drill-down and security incidents.',
      side: 'right',
    },
  },
  {
    element: '[data-tour="start-reviewing"]',
    popover: {
      title: 'Jump in',
      description:
        'Open a check, review the image and AI-detected flags, then record a decision. That’s the loop. Enjoy the demo!',
      side: 'top',
    },
  },
];

function buildDriver() {
  const steps = STEPS.filter((s) => !s.element || document.querySelector(s.element as string));
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

/** Start the guided tour on demand (e.g. from the "Take a tour" button). */
export function startProductTour() {
  buildDriver().drive();
}

/**
 * Auto-start the tour once per browser (forced on first demo visit), then leave
 * it available via the header button. Call after the dashboard has rendered.
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
  setTimeout(() => startProductTour(), 700);
}
