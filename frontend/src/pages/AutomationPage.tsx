import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import {
  BoltIcon,
  ShieldCheckIcon,
  BanknotesIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';
import BackLink from '../components/common/BackLink';
import { useAutomationStore, type AutomationMode } from '../stores/automationStore';
import { useAutomationSimulation } from '../hooks/useAutomationSimulation';

const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
const money = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${Math.round(n).toLocaleString()}`;

const MODES: { value: AutomationMode; label: string; blurb: string }[] = [
  { value: 'off', label: 'Off', blurb: 'Every item is reviewed by a person.' },
  {
    value: 'shadow',
    label: 'Shadow',
    blurb: 'The policy runs silently and is scored against reviewer decisions — nothing is auto-actioned. Recommended before going live.',
  },
  {
    value: 'active',
    label: 'Active',
    blurb: 'Eligible low-risk items are auto-cleared inline; only exceptions reach a reviewer.',
  },
];

export default function AutomationPage() {
  const {
    mode,
    setMode,
    autoClearMaxTier,
    setAutoClearMaxTier,
    amountCap,
    setAmountCap,
  } = useAutomationStore();
  const sim = useAutomationSimulation();

  const dispositionData = [
    { name: 'Auto-clear', value: sim.autoClearCount, color: '#22c55e' },
    { name: 'Needs review', value: sim.reviewCount, color: '#3b82f6' },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6">
      <BackLink to="/operations" label="Back to Operations" />

      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <BoltIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
          Decision Automation
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-gray-600">
          Straight-through processing for low-risk items: auto-clear the obvious-good so reviewers
          spend their time only on the exceptions that need judgment. Figures below are a live
          simulation over current demo items and historical reviewer decisions.
        </p>
      </div>

      {/* Headline metrics */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <BoltIcon className="h-4 w-4 text-green-600" /> Straight-through rate
          </div>
          <p className="mt-2 text-3xl font-bold text-gray-900">{pct(sim.stpRate)}</p>
          <p className="text-xs text-gray-500">
            {sim.autoClearCount} of {sim.openTotal} current items auto-cleared
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <ShieldCheckIcon className="h-4 w-4 text-primary-600" /> Shadow accuracy
          </div>
          <p className="mt-2 text-3xl font-bold text-gray-900">
            {sim.shadowConsidered > 0 ? pct(sim.shadowAccuracy) : '—'}
          </p>
          <p className="text-xs text-gray-500">
            Agreement with reviewers on items it would auto-clear
          </p>
        </div>
        <Link
          to="/reports"
          className="group rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md hover:ring-1 hover:ring-primary-200"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <BanknotesIcon className="h-4 w-4 text-emerald-600" /> Est. annual value
          </div>
          <p className="mt-2 text-3xl font-bold text-gray-900">{money(sim.roi.totalAnnualValue)}</p>
          <p className="flex items-center gap-1 text-xs text-primary-600 group-hover:underline">
            Full ROI breakdown on Reports <ArrowRightIcon className="h-3 w-3" />
          </p>
        </Link>
      </div>

      {/* Mode selector */}
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900">Automation mode</h2>
        <div className="mt-3 inline-flex rounded-lg border border-gray-300 p-0.5">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                mode === m.value ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-gray-500">{MODES.find((m) => m.value === mode)?.blurb}</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Policy controls */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-gray-900">Auto-clear policy</h2>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700">Maximum risk tier</label>
            <div className="mt-2 inline-flex rounded-lg border border-gray-300 p-0.5">
              {(['low', 'medium'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setAutoClearMaxTier(t)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                    autoClearMaxTier === t ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {t === 'low' ? 'Low only' : 'Low + Medium'}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <label htmlFor="cap" className="block text-sm font-medium text-gray-700">
              Amount cap
            </label>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-gray-500">$</span>
              <input
                id="cap"
                type="number"
                min={0}
                step={500}
                value={amountCap}
                onChange={(e) => setAmountCap(Number(e.target.value))}
                className="w-40 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              />
            </div>
            <input
              type="range"
              min={0}
              max={25000}
              step={500}
              value={Math.min(amountCap, 25000)}
              onChange={(e) => setAmountCap(Number(e.target.value))}
              className="mt-2 w-full"
              aria-label="Amount cap slider"
            />
          </div>

          <div className="mt-5 border-t border-gray-100 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Guardrails — always reviewed by a person
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {['Dual-control items', 'Over the amount cap', 'Above the risk tier'].map(
                (g) => (
                  <span
                    key={g}
                    className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800"
                  >
                    <ShieldCheckIcon className="h-3.5 w-3.5" /> {g}
                  </span>
                )
              )}
            </div>
          </div>
        </div>

        {/* Disposition */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-gray-900">Current queue disposition</h2>
          {sim.openTotal === 0 ? (
            <p className="py-12 text-center text-sm text-gray-500">No open items to simulate.</p>
          ) : (
            <div className="mt-2 flex items-center gap-6">
              <div className="relative h-44 w-44 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={dispositionData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={2}
                    >
                      {dispositionData.map((d) => (
                        <Cell key={d.name} fill={d.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number, n: string) => [`${v} items`, n]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-gray-900">{pct(sim.stpRate)}</span>
                  <span className="text-[11px] text-gray-500">auto</span>
                </div>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
                  <span className="text-gray-600">Auto-clear</span>
                  <span className="ml-auto font-semibold text-gray-900">{sim.autoClearCount}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                  <span className="text-gray-600">Needs review</span>
                  <span className="ml-auto font-semibold text-gray-900">{sim.reviewCount}</span>
                </div>
                <p className="pt-2 text-xs text-gray-500">
                  {sim.guardrailHeld} item(s) held for dual control. AI flags are advisory and inform
                  the risk tier.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Shadow validation */}
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900">Shadow validation</h2>
        <p className="mt-1 text-sm text-gray-500">
          The policy replayed against {sim.shadowConsidered} historical items it would have auto-cleared,
          compared to what reviewers actually decided.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-green-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-green-800">
              <CheckCircleIcon className="h-4 w-4" /> Agreed with reviewer
            </div>
            <p className="mt-1 text-2xl font-bold text-green-700">
              {sim.shadowAgreements}
              <span className="ml-1 text-sm font-medium text-green-700/70">
                / {sim.shadowConsidered}
              </span>
            </p>
          </div>
          <div className="rounded-lg bg-red-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-red-800">
              <ShieldCheckIcon className="h-4 w-4" /> Would-be exceptions
            </div>
            <p className="mt-1 text-2xl font-bold text-red-700">{sim.shadowMisses}</p>
            <p className="text-xs text-red-700/80">{money(sim.shadowMissAmount)} at risk — tighten the policy or stay in Shadow.</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-blue-800">
              <UserGroupIcon className="h-4 w-4" /> Exceptions routed to people
            </div>
            <p className="mt-1 text-2xl font-bold text-blue-700">
              {sim.exceptionsCaught}
              <span className="ml-1 text-sm font-medium text-blue-700/70">/ {sim.exceptionsTotal}</span>
            </p>
            <p className="text-xs text-blue-700/80">of historical returns/rejects correctly kept human.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
