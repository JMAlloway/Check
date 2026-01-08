import { useEffect, useState } from 'react';
import { XMarkIcon, BeakerIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { useDemoStore } from '../../stores/demoStore';
import clsx from 'clsx';

interface DemoBannerProps {
  variant?: 'full' | 'compact';
  dismissible?: boolean;
}

export default function DemoBanner({ variant = 'full', dismissible = true }: DemoBannerProps) {
  const { status, fetchDemoStatus, isDemoMode } = useDemoStore();
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    fetchDemoStatus();
  }, [fetchDemoStatus]);

  // Don't render if not in demo mode or dismissed
  if (!isDemoMode() || dismissed) {
    return null;
  }

  if (variant === 'compact') {
    return (
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="flex items-center justify-center gap-2 px-4 py-1.5 text-sm text-amber-800">
          <BeakerIcon className="h-4 w-4" />
          <span className="font-medium">Demo Mode</span>
          <span className="text-amber-600">- Using synthetic data</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border-b-2 border-amber-300">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
              <BeakerIcon className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="font-semibold text-amber-900">
                Demo Mode Active
              </p>
              <p className="text-sm text-amber-700">
                You are viewing synthetic data for demonstration purposes.
                No real PII or production data is being used.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 text-sm text-amber-700">
              <InformationCircleIcon className="h-4 w-4" />
              <span>Environment: <span className="font-medium">{status?.environment}</span></span>
            </div>

            {dismissible && (
              <button
                type="button"
                onClick={() => setDismissed(true)}
                className="rounded-md p-1.5 text-amber-600 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>

        {/* Feature indicators */}
        {status?.features && (
          <div className="mt-3 flex flex-wrap gap-2">
            {status.features.synthetic_checks && (
              <DemoFeatureTag label="Synthetic Checks" />
            )}
            {status.features.mock_ai_analysis && (
              <DemoFeatureTag label="Mock AI" />
            )}
            {status.features.demo_images && (
              <DemoFeatureTag label="Demo Images" />
            )}
            {status.features.guided_tour && (
              <DemoFeatureTag label="Guided Tour" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DemoFeatureTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 border border-amber-200">
      {label}
    </span>
  );
}

// Badge variant for inline use
export function DemoBadge({ className }: { className?: string }) {
  const { isDemoMode } = useDemoStore();

  if (!isDemoMode()) {
    return null;
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 border border-amber-200',
        className
      )}
    >
      <BeakerIcon className="h-3 w-3" />
      DEMO
    </span>
  );
}

// Indicator for sidebar/header
export function DemoIndicator() {
  const { isDemoMode, status } = useDemoStore();

  if (!isDemoMode()) {
    return null;
  }

  return (
    <div className="flex items-center gap-1.5 rounded-md bg-amber-500/20 px-2 py-1 text-xs font-medium text-amber-200">
      <BeakerIcon className="h-3.5 w-3.5" />
      <span>DEMO</span>
    </div>
  );
}
