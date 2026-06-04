import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ShieldExclamationIcon,
  ArrowPathIcon,
  PaperAirplaneIcon,
  ArrowUturnLeftIcon,
} from '@heroicons/react/24/outline';
import { fraudApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { humanizeLabel } from '../utils/labels';
import ConfirmationModal from '../components/common/ConfirmationModal';
import type { FraudEventListItem } from '../types';

const STATUS_TONE: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  submitted: 'bg-blue-100 text-blue-800',
  withdrawn: 'bg-amber-100 text-amber-800',
};

function titleCase(s: string): string {
  return humanizeLabel(s);
}

function currency(v: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(parseFloat(v));
}

function WithdrawModal({
  event,
  onClose,
  onDone,
}: {
  event: FraudEventListItem;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState('');
  const trapRef = useFocusTrap<HTMLDivElement>(true, onClose);
  const mut = useMutation({
    mutationFn: () => fraudApi.withdrawEvent(event.id, reason),
    onSuccess: () => {
      toast.success('Fraud event withdrawn');
      onDone();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Withdraw failed');
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Withdraw fraud event"
    >
      <div ref={trapRef} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h2 className="text-base font-semibold text-gray-900">Withdraw fraud event</h2>
        <p className="mt-1 text-sm text-gray-600">
          Withdraw the {titleCase(event.fraud_type)} event from network sharing. A reason is
          required for the audit trail.
        </p>
        <textarea
          className="mt-3 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for withdrawal (min 5 chars)"
        />
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="text-sm font-medium text-gray-500 hover:text-gray-700">
            Cancel
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={reason.trim().length < 5 || mut.isPending}
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {mut.isPending ? 'Withdrawing…' : 'Withdraw'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function FraudEventsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();
  const canSubmit = hasPermission('fraud', 'submit');
  const canWithdraw = hasPermission('fraud', 'withdraw');
  const [withdrawing, setWithdrawing] = useState<FraudEventListItem | null>(null);
  const [submitting, setSubmitting] = useState<FraudEventListItem | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['fraud-events'],
    queryFn: () => fraudApi.getEvents({ page_size: 100 }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['fraud-events'] });

  const submit = useMutation({
    mutationFn: (id: string) => fraudApi.submitEvent(id, { sharing_level: 1, confirm_no_pii: true }),
    onSuccess: () => {
      toast.success('Submitted to network');
      invalidate();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Submit failed');
    },
  });

  const events: FraudEventListItem[] = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ShieldExclamationIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
            Fraud Events
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Reported fraud events and their network-sharing lifecycle (draft → submitted →
            withdrawn).
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowPathIcon className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white">
        {isLoading && <div className="p-6 text-sm text-gray-500">Loading fraud events…</div>}

        {isError && !isLoading && (
          <div className="p-6 text-center">
            <p className="text-sm text-red-800">Could not load fraud events.</p>
            <button
              onClick={() => refetch()}
              className="mt-2 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !isError && events.length === 0 && (
          <div className="p-10 text-center text-sm text-gray-500">No fraud events reported.</div>
        )}

        {events.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-500">
                  <th className="px-5 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Channel</th>
                  <th className="px-3 py-2 font-medium">Amount</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id} className="border-t border-gray-100">
                    <td className="whitespace-nowrap px-5 py-2 text-gray-500">
                      {new Date(ev.event_date).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2 text-gray-800">{titleCase(ev.fraud_type)}</td>
                    <td className="px-3 py-2 text-gray-600">{titleCase(ev.channel)}</td>
                    <td className="px-3 py-2 font-medium text-gray-900">{currency(ev.amount)}</td>
                    <td className="px-3 py-2 text-gray-600">{ev.confidence}%</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_TONE[ev.status] ?? 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {titleCase(ev.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {ev.status === 'draft' && canSubmit && (
                        <button
                          onClick={() => setSubmitting(ev)}
                          disabled={submit.isPending}
                          className="inline-flex items-center gap-1 rounded-lg bg-primary-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                        >
                          <PaperAirplaneIcon className="h-3.5 w-3.5" aria-hidden="true" />
                          Submit
                        </button>
                      )}
                      {ev.status === 'submitted' && canWithdraw && (
                        <button
                          onClick={() => setWithdrawing(ev)}
                          className="inline-flex items-center gap-1 rounded-lg border border-amber-300 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50"
                        >
                          <ArrowUturnLeftIcon className="h-3.5 w-3.5" aria-hidden="true" />
                          Withdraw
                        </button>
                      )}
                      {ev.status === 'withdrawn' && <span className="text-xs text-gray-400">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {withdrawing && (
        <WithdrawModal
          event={withdrawing}
          onClose={() => setWithdrawing(null)}
          onDone={() => {
            setWithdrawing(null);
            invalidate();
          }}
        />
      )}

      <ConfirmationModal
        isOpen={!!submitting}
        onClose={() => setSubmitting(null)}
        onConfirm={() => {
          if (submitting) submit.mutate(submitting.id);
          setSubmitting(null);
        }}
        title="Submit fraud event to network"
        message="This shares the event with the fraud-intelligence network. Confirm the details are correct and contain no PII before submitting."
        confirmText="Submit to network"
        cancelText="Cancel"
        isPending={submit.isPending}
        details={
          submitting
            ? [
                { label: 'Type', value: humanizeLabel(submitting.fraud_type) },
                { label: 'Amount', value: `$${submitting.amount.toLocaleString()}` },
              ]
            : undefined
        }
      />
    </div>
  );
}
