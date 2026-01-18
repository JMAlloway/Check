import { useState } from 'react';
import {
  BookOpenIcon,
  QuestionMarkCircleIcon,
  AcademicCapIcon,
  ShieldCheckIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

type TabId = 'getting-started' | 'definitions' | 'workflows' | 'roles' | 'faq';

interface Tab {
  id: TabId;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: Tab[] = [
  { id: 'getting-started', name: 'Getting Started', icon: AcademicCapIcon },
  { id: 'definitions', name: 'Definitions', icon: BookOpenIcon },
  { id: 'workflows', name: 'Workflows', icon: DocumentTextIcon },
  { id: 'roles', name: 'Roles & Permissions', icon: ShieldCheckIcon },
  { id: 'faq', name: 'FAQ', icon: QuestionMarkCircleIcon },
];

// Collapsible section component
function Section({
  title,
  children,
  defaultOpen = false
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-gray-200 last:border-b-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium text-gray-900">{title}</span>
        {isOpen ? (
          <ChevronDownIcon className="h-5 w-5 text-gray-500" />
        ) : (
          <ChevronRightIcon className="h-5 w-5 text-gray-500" />
        )}
      </button>
      {isOpen && (
        <div className="pb-4 text-gray-600 prose prose-sm max-w-none">
          {children}
        </div>
      )}
    </div>
  );
}

// Definition item component
function Definition({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-gray-100 last:border-b-0">
      <dt className="font-semibold text-gray-900">{term}</dt>
      <dd className="mt-1 text-gray-600">{children}</dd>
    </div>
  );
}

// Getting Started content
function GettingStartedTab() {
  return (
    <div className="space-y-6">
      <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
        <h3 className="font-semibold text-blue-900">Welcome to Check Review Console</h3>
        <p className="mt-2 text-blue-800">
          This guide will help you navigate the system and understand key workflows.
        </p>
      </div>

      <Section title="1. Logging In" defaultOpen>
        <ul className="list-disc ml-4 space-y-2">
          <li>Enter your username and password on the login screen</li>
          <li>If MFA is enabled, enter your 6-digit code from your authenticator app</li>
          <li>Your session will remain active for 30 minutes of inactivity</li>
          <li>For security, sessions automatically refresh while you&apos;re active</li>
        </ul>
      </Section>

      <Section title="2. Understanding the Dashboard">
        <p>The dashboard provides an at-a-glance view of your workload:</p>
        <ul className="list-disc ml-4 space-y-2 mt-2">
          <li><strong>Pending Items:</strong> Checks waiting in all queues</li>
          <li><strong>Processed Today:</strong> Checks you&apos;ve reviewed today</li>
          <li><strong>SLA Breached:</strong> Items past their service level target</li>
          <li><strong>Dual Control Pending:</strong> Items waiting for secondary approval</li>
        </ul>
        <p className="mt-2">Click any stat to filter the queue to those items.</p>
      </Section>

      <Section title="3. Working the Review Queue">
        <ol className="list-decimal ml-4 space-y-2">
          <li>Navigate to <strong>Review Queue</strong> from the sidebar</li>
          <li>Items are sorted by priority (SLA breach risk)</li>
          <li>Click an item to open it for review</li>
          <li>Review the check images, MICR data, and risk flags</li>
          <li>Make your decision: Approve, Return, Hold, or Escalate</li>
          <li>Add notes if required and submit</li>
        </ol>
      </Section>

      <Section title="4. Keyboard Shortcuts">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="bg-gray-50 p-2 rounded"><code>A</code> - Approve</div>
          <div className="bg-gray-50 p-2 rounded"><code>R</code> - Return</div>
          <div className="bg-gray-50 p-2 rounded"><code>H</code> - Hold</div>
          <div className="bg-gray-50 p-2 rounded"><code>E</code> - Escalate</div>
          <div className="bg-gray-50 p-2 rounded"><code>N</code> - Next Item</div>
          <div className="bg-gray-50 p-2 rounded"><code>P</code> - Previous Item</div>
          <div className="bg-gray-50 p-2 rounded"><code>Z</code> - Zoom Image</div>
          <div className="bg-gray-50 p-2 rounded"><code>F</code> - Flip (Front/Back)</div>
        </div>
      </Section>
    </div>
  );
}

// Definitions content
function DefinitionsTab() {
  const [searchTerm, setSearchTerm] = useState('');

  const definitions = [
    { term: 'On-Us Check', definition: 'A check drawn on the same bank where it is being deposited. Can be processed immediately without going through the Federal Reserve.' },
    { term: 'Transit Check', definition: 'A check drawn on a different bank than where it is being deposited. Must be routed through the banking system for collection.' },
    { term: 'MICR Line', definition: 'Magnetic Ink Character Recognition - the machine-readable line at the bottom of checks containing routing number, account number, and check number.' },
    { term: 'Dual Control', definition: 'A security requirement where two authorized individuals must independently approve a transaction. Used for high-value or high-risk items.' },
    { term: 'Hold', definition: 'A temporary delay placed on funds availability. The deposited amount is not available for withdrawal until the hold expires or is released.' },
    { term: 'Release', definition: 'Making held funds available before the standard hold period expires. May require authorization.' },
    { term: 'SLA (Service Level Agreement)', definition: 'The expected time to complete check review from presentation. Measured in hours from queue entry to decision.' },
    { term: 'Reason Code', definition: 'A standardized code explaining why a check was approved, returned, or held. Used for audit trails and reporting.' },
    { term: 'Risk Level', definition: 'Assessment of potential fraud or loss risk: Low (standard), Medium (careful review), High (may require dual control), Critical (immediate attention).' },
    { term: 'Network Alert', definition: 'Notification from the inter-bank fraud sharing network that this check or related indicators have been flagged by another institution.' },
    { term: 'Audit Packet', definition: 'A comprehensive record including check images, MICR data, decision history, notes, detection analysis, and any fraud alerts.' },
    { term: 'Override', definition: 'When a reviewer makes a decision that differs from a detection rule recommendation. Requires documented justification.' },
    { term: 'Presented Date', definition: 'The date a check was submitted for deposit or cashing - when the item enters the processing queue.' },
    { term: 'Posted Date', definition: 'The date a check was officially credited to or debited from an account. May differ from presented date.' },
    { term: 'Account Tenure', definition: 'How long the account has been open. New accounts (< 90 days) often receive additional scrutiny.' },
    { term: 'RDC (Remote Deposit Capture)', definition: 'Mobile or scanner-based deposit where the check image is captured remotely rather than at a branch.' },
    { term: 'Endorsement', definition: 'The signature on the back of a check authorizing the deposit or transfer of funds.' },
    { term: 'Maker', definition: 'The person or entity who writes the check (the payer).' },
    { term: 'Payee', definition: 'The person or entity to whom the check is written (the recipient).' },
    { term: 'Drawer', definition: 'The bank on which the check is drawn (where the maker has their account).' },
  ];

  const filteredDefinitions = definitions.filter(
    d => d.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
         d.definition.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search definitions..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        />
      </div>

      <dl className="divide-y divide-gray-100">
        {filteredDefinitions.map((item) => (
          <Definition key={item.term} term={item.term}>
            {item.definition}
          </Definition>
        ))}
        {filteredDefinitions.length === 0 && (
          <p className="py-4 text-gray-500 text-center">No matching definitions found.</p>
        )}
      </dl>
    </div>
  );
}

// Workflows content
function WorkflowsTab() {
  return (
    <div className="space-y-6">
      <Section title="Standard Check Review" defaultOpen>
        <ol className="list-decimal ml-4 space-y-3">
          <li>
            <strong>Claim or receive item</strong>
            <p className="text-sm text-gray-500">Items are assigned based on queue rules or can be claimed manually</p>
          </li>
          <li>
            <strong>Review check images</strong>
            <p className="text-sm text-gray-500">Verify front image (payee, amount, signature) and back (endorsements)</p>
          </li>
          <li>
            <strong>Verify MICR data</strong>
            <p className="text-sm text-gray-500">Confirm routing number, account number match the check</p>
          </li>
          <li>
            <strong>Check risk indicators</strong>
            <p className="text-sm text-gray-500">Review detection flags, network alerts, and account history</p>
          </li>
          <li>
            <strong>Make decision</strong>
            <p className="text-sm text-gray-500">Approve, Return (with reason code), Hold, or Escalate</p>
          </li>
          <li>
            <strong>Add notes if required</strong>
            <p className="text-sm text-gray-500">Document any concerns or justifications</p>
          </li>
        </ol>
      </Section>

      <Section title="Dual Control Workflow">
        <div className="bg-amber-50 p-3 rounded-lg mb-3 text-sm">
          <strong>When required:</strong> High-value items, high-risk flags, network alerts, detection rule overrides
        </div>
        <ol className="list-decimal ml-4 space-y-2">
          <li><strong>First reviewer</strong> makes initial decision (Approve/Return/Hold)</li>
          <li>Item moves to <strong>Pending Dual Control</strong> queue</li>
          <li><strong>Second reviewer (Approver)</strong> reviews the item and first decision</li>
          <li>Approver can <strong>Confirm</strong> or <strong>Reject</strong> the decision</li>
          <li>If rejected, item returns to first reviewer with feedback</li>
        </ol>
      </Section>

      <Section title="Escalation Workflow">
        <ol className="list-decimal ml-4 space-y-2">
          <li>Reviewer cannot resolve an issue at their level</li>
          <li>Select <strong>Escalate</strong> and choose target queue (e.g., Management Review)</li>
          <li>Add detailed escalation reason</li>
          <li>Item appears in the escalation queue for senior review</li>
          <li>Senior reviewer makes final decision</li>
        </ol>
      </Section>

      <Section title="Hold & Release Workflow">
        <div className="space-y-3">
          <div>
            <h4 className="font-medium">Placing a Hold:</h4>
            <ol className="list-decimal ml-4 text-sm">
              <li>Select Hold decision</li>
              <li>Choose hold type (Standard, Exception, Case-by-Case)</li>
              <li>Specify duration or release date</li>
              <li>Document reason for hold</li>
            </ol>
          </div>
          <div>
            <h4 className="font-medium">Releasing a Hold:</h4>
            <ol className="list-decimal ml-4 text-sm">
              <li>Find item in Held Items queue</li>
              <li>Click Release</li>
              <li>For large amounts, may require dual control</li>
              <li>Document reason for early release</li>
            </ol>
          </div>
        </div>
      </Section>

      <Section title="Fraud Alert Response">
        <ol className="list-decimal ml-4 space-y-2">
          <li>Network alert appears on check item</li>
          <li>Review alert details: severity, indicator type, match count</li>
          <li>Cross-reference with account history and check details</li>
          <li>If legitimate concern: Return with fraud reason code</li>
          <li>If false positive: Approver can dismiss with documented reason</li>
          <li>For confirmed fraud: Create fraud event for network sharing</li>
        </ol>
      </Section>
    </div>
  );
}

// Roles content
function RolesTab() {
  return (
    <div className="space-y-6">
      <p className="text-gray-600">
        Access to features is controlled by your assigned role. Contact your administrator
        if you need different permissions.
      </p>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Permission
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Reviewer
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Approver
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Admin
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Auditor
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {[
              { name: 'View check items & images', reviewer: true, approver: true, admin: true, auditor: true },
              { name: 'Make decisions (within limit)', reviewer: true, approver: true, admin: true, auditor: false },
              { name: 'Dual control approval', reviewer: false, approver: true, admin: true, auditor: false },
              { name: 'Override detection rules', reviewer: false, approver: true, admin: true, auditor: false },
              { name: 'Dismiss fraud alerts', reviewer: false, approver: true, admin: true, auditor: false },
              { name: 'Export audit packets', reviewer: false, approver: true, admin: true, auditor: true },
              { name: 'View all audit logs', reviewer: false, approver: true, admin: true, auditor: true },
              { name: 'Manage users', reviewer: false, approver: false, admin: true, auditor: false },
              { name: 'Configure policies', reviewer: false, approver: false, admin: true, auditor: false },
              { name: 'Manage queues', reviewer: false, approver: false, admin: true, auditor: false },
            ].map((row) => (
              <tr key={row.name}>
                <td className="px-4 py-3 text-sm text-gray-900">{row.name}</td>
                <td className="px-4 py-3 text-center">
                  {row.reviewer ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">–</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  {row.approver ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">–</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  {row.admin ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">–</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  {row.auditor ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-gray-300">–</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Section title="Role Descriptions">
        <dl className="space-y-4">
          <div>
            <dt className="font-semibold">Reviewer</dt>
            <dd className="text-sm">Day-to-day check processor. Reviews items, makes decisions within their limit, adds notes. Cannot approve dual control items or override detection rules.</dd>
          </div>
          <div>
            <dt className="font-semibold">Approver (Senior Reviewer)</dt>
            <dd className="text-sm">Experienced reviewer with elevated limits. Can approve dual control items, override detection rule recommendations, dismiss fraud alerts, and export audit packets.</dd>
          </div>
          <div>
            <dt className="font-semibold">Administrator</dt>
            <dd className="text-sm">Full system access. Manages users, roles, policies, queues, and connectors. Can perform all reviewer and approver functions.</dd>
          </div>
          <div>
            <dt className="font-semibold">Auditor</dt>
            <dd className="text-sm">Read-only access for compliance and examination. Can view all items, history, and logs but cannot make changes or decisions.</dd>
          </div>
        </dl>
      </Section>
    </div>
  );
}

// FAQ content
function FAQTab() {
  const faqs = [
    {
      q: 'What does the risk level indicator mean?',
      a: 'Risk levels are assessed based on multiple factors including amount, account tenure, AI analysis, and network alerts. LOW = standard processing, MEDIUM = careful review, HIGH = may require dual control, CRITICAL = immediate attention needed.'
    },
    {
      q: 'Why is dual control required for some items?',
      a: 'Dual control is triggered by high-value checks (above threshold), high-risk indicators, network fraud alerts, AI overrides, or policy rules. It ensures two sets of eyes review sensitive decisions.'
    },
    {
      q: 'What should I do if I see a network fraud alert?',
      a: 'Review the alert details carefully. Cross-reference with the account history and check details. If the concern is legitimate, return the check with an appropriate fraud reason code. If it appears to be a false positive, escalate to an approver who can dismiss it.'
    },
    {
      q: 'How long are holds typically placed?',
      a: 'Hold periods vary: Reg CC standard holds are 2-5 business days depending on check type. Exception holds can be longer (up to 7 days for new accounts). Case-by-case holds are determined by the reviewer based on specific circumstances.'
    },
    {
      q: 'Can I override an AI recommendation?',
      a: 'Reviewers cannot override AI recommendations directly. If you disagree with an AI flag, escalate the item or contact an Approver. Approvers can override AI with documented justification.'
    },
    {
      q: 'What happens when I escalate an item?',
      a: 'The item moves to the selected escalation queue (e.g., Management Review). Your notes are preserved. A senior reviewer will make the final decision. You&apos;ll see the resolution in the item history.'
    },
    {
      q: 'Why was my session logged out?',
      a: 'Sessions expire after 30 minutes of inactivity for security. If you changed your password, all sessions are invalidated. If you suspect unauthorized access, contact your administrator.'
    },
    {
      q: 'How do I export an audit packet?',
      a: 'Open the check item, click the "Export" button in the toolbar, and select "Audit Packet". The PDF will include all images, MICR data, decision history, notes, and alerts. Approvers and Auditors have this permission.'
    },
    {
      q: 'What is the SLA timer based on?',
      a: 'The SLA timer starts when an item enters a queue (presented date) and counts toward the queue&apos;s configured SLA target. High Priority queues typically have shorter SLAs (2 hours) than Standard queues (4 hours).'
    },
    {
      q: 'How do I report a suspected fraud?',
      a: 'After returning a check with a fraud-related reason code, Administrators can create a Fraud Event to share indicators with the network. This helps other institutions identify similar fraud patterns.'
    },
  ];

  return (
    <div className="space-y-4">
      {faqs.map((faq, index) => (
        <Section key={index} title={faq.q}>
          <p>{faq.a}</p>
        </Section>
      ))}
    </div>
  );
}

export default function HelpPage() {
  const [activeTab, setActiveTab] = useState<TabId>('getting-started');

  const renderContent = () => {
    switch (activeTab) {
      case 'getting-started':
        return <GettingStartedTab />;
      case 'definitions':
        return <DefinitionsTab />;
      case 'workflows':
        return <WorkflowsTab />;
      case 'roles':
        return <RolesTab />;
      case 'faq':
        return <FAQTab />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Help Center</h1>
        <p className="mt-1 text-gray-500">
          Learn how to use the Check Review Console effectively
        </p>
      </div>

      {/* Tab navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <tab.icon className="h-5 w-5 mr-2" />
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-lg shadow p-6">
        {renderContent()}
      </div>

      {/* Contact support footer */}
      <div className="bg-gray-50 rounded-lg p-4 text-center text-sm text-gray-600">
        <p>
          Can&apos;t find what you&apos;re looking for?{' '}
          <a href="mailto:support@example.com" className="text-primary-600 hover:underline">
            Contact Support
          </a>
        </p>
      </div>
    </div>
  );
}
