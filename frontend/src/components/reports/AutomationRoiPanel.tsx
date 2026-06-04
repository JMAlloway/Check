import { Link } from 'react-router-dom';
import { BoltIcon, ArrowRightIcon } from '@heroicons/react/24/outline';
import { useAutomationStore } from '../../stores/automationStore';
import { useAutomationSimulation } from '../../hooks/useAutomationSimulation';

const money = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(2)}M` : `$${Math.round(n).toLocaleString()}`;

function AssumptionInput({
  label,
  value,
  onChange,
  prefix,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  prefix?: string;
  step?: number;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <div className="mt-1 flex items-center gap-1 rounded-lg border border-gray-300 px-2 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500">
        {prefix && <span className="text-sm text-gray-400">{prefix}</span>}
        <input
          type="number"
          min={0}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full border-0 py-1.5 text-sm focus:outline-none focus:ring-0"
        />
      </div>
    </label>
  );
}

export default function AutomationRoiPanel() {
  const {
    annualVolume,
    avgHandleTimeSec,
    loadedCostPerMin,
    annualFraudPrevented,
    setAssumption,
  } = useAutomationStore();
  const { stpRate, roi } = useAutomationSimulation();

  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50/40 p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
          <BoltIcon className="h-5 w-5 text-emerald-600" /> Automation value
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            Estimate
          </span>
        </h2>
        <Link
          to="/automation"
          className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:underline"
        >
          Tune the policy <ArrowRightIcon className="h-3.5 w-3.5" />
        </Link>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Assumptions */}
        <div className="grid grid-cols-2 gap-3">
          <AssumptionInput
            label="Annual check volume"
            value={annualVolume}
            step={50000}
            onChange={(v) => setAssumption('annualVolume', v)}
          />
          <AssumptionInput
            label="Avg handle time (sec)"
            value={avgHandleTimeSec}
            step={5}
            onChange={(v) => setAssumption('avgHandleTimeSec', v)}
          />
          <AssumptionInput
            label="Loaded cost / min"
            prefix="$"
            value={loadedCostPerMin}
            step={0.05}
            onChange={(v) => setAssumption('loadedCostPerMin', v)}
          />
          <AssumptionInput
            label="Fraud prevented / yr"
            prefix="$"
            value={annualFraudPrevented}
            step={50000}
            onChange={(v) => setAssumption('annualFraudPrevented', v)}
          />
        </div>

        {/* Outputs */}
        <div className="flex flex-col justify-between rounded-lg border border-emerald-200 bg-white p-4">
          <div>
            <p className="text-sm text-gray-500">Estimated annual value</p>
            <p className="text-3xl font-bold text-emerald-700">{money(roi.totalAnnualValue)}</p>
          </div>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Straight-through rate</dt>
              <dd className="font-semibold text-gray-900">{(stpRate * 100).toFixed(0)}%</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Labor saved</dt>
              <dd className="font-semibold text-gray-900">{money(roi.laborSavedPerYear)}/yr</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Reviewer capacity freed</dt>
              <dd className="font-semibold text-gray-900">
                {Math.round(roi.hoursFreedPerYear).toLocaleString()} hrs (≈ {roi.ftesFreed.toFixed(1)} FTE)
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Fraud prevented</dt>
              <dd className="font-semibold text-gray-900">{money(roi.fraudPreventedPerYear)}/yr</dd>
            </div>
          </dl>
        </div>
      </div>
      <p className="mt-3 text-xs text-gray-500">
        Labor savings = annual volume × straight-through rate × handle time × loaded cost. Straight-through
        rate is simulated live from current items; assumptions above are editable estimates.
      </p>
    </div>
  );
}
