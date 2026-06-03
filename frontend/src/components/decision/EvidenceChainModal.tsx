import { useQuery } from '@tanstack/react-query';
import {
  ShieldCheckIcon,
  ShieldExclamationIcon,
  XMarkIcon,
  CheckBadgeIcon,
} from '@heroicons/react/24/outline';
import { decisionApi } from '../../services/api';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import type { EvidenceChainResult } from '../../types';

interface EvidenceChainModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemId: string;
}

function ResultRow({ result, index }: { result: EvidenceChainResult; index: number }) {
  const ok = result.hash_valid === true && result.chain_valid === true;
  return (
    <li className="flex items-start gap-3 rounded-md border border-gray-100 bg-gray-50 p-3">
      <div className={`mt-0.5 ${ok ? 'text-green-600' : 'text-red-600'}`}>
        {ok ? (
          <CheckBadgeIcon className="h-5 w-5" aria-hidden="true" />
        ) : (
          <ShieldExclamationIcon className="h-5 w-5" aria-hidden="true" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-gray-900">Decision {index + 1}</span>
          <span className="font-mono text-xs text-gray-500">
            {result.decision_id.slice(0, 8)}…
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-600">
          <span>
            Hash:{' '}
            <span className={result.hash_valid ? 'text-green-700' : 'text-red-700'}>
              {result.hash_valid === null ? 'n/a' : result.hash_valid ? 'valid' : 'invalid'}
            </span>
          </span>
          <span>
            Chain link:{' '}
            <span className={result.chain_valid ? 'text-green-700' : 'text-red-700'}>
              {result.chain_valid === null ? 'n/a' : result.chain_valid ? 'intact' : 'broken'}
            </span>
          </span>
          {result.created_at && <span>{new Date(result.created_at).toLocaleString()}</span>}
        </div>
        {result.error && <p className="mt-1 text-xs text-red-700">{result.error}</p>}
      </div>
    </li>
  );
}

export default function EvidenceChainModal({ isOpen, onClose, itemId }: EvidenceChainModalProps) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['evidence-chain', itemId],
    queryFn: () => decisionApi.verifyEvidenceChain(itemId),
    enabled: isOpen,
  });

  const trapRef = useFocusTrap<HTMLDivElement>(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Evidence chain verification"
    >
      <div
        ref={trapRef}
        className="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
            <ShieldCheckIcon className="h-5 w-5 text-primary-600" aria-hidden="true" />
            Evidence Chain Verification
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
          {isLoading && (
            <div className="py-8 text-center text-sm text-gray-500">Verifying integrity…</div>
          )}

          {isError && !isLoading && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
              <p className="text-sm text-red-800">Verification request failed.</p>
              <button
                onClick={() => refetch()}
                className="mt-2 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          )}

          {data && !isLoading && (
            <>
              <div
                className={`mb-4 flex items-center gap-3 rounded-lg border p-4 ${
                  data.chain_valid
                    ? 'border-green-200 bg-green-50'
                    : 'border-red-200 bg-red-50'
                }`}
              >
                {data.chain_valid ? (
                  <ShieldCheckIcon className="h-8 w-8 text-green-600" aria-hidden="true" />
                ) : (
                  <ShieldExclamationIcon className="h-8 w-8 text-red-600" aria-hidden="true" />
                )}
                <div>
                  <p
                    className={`text-sm font-semibold ${
                      data.chain_valid ? 'text-green-900' : 'text-red-900'
                    }`}
                  >
                    {data.chain_valid
                      ? 'Chain verified — tamper-evident and intact'
                      : 'Chain verification failed'}
                  </p>
                  <p className="text-xs text-gray-600">
                    {data.total_decisions} decision{data.total_decisions === 1 ? '' : 's'} in chain
                  </p>
                </div>
              </div>

              {data.verification_results.length === 0 ? (
                <p className="py-4 text-center text-sm text-gray-500">
                  No sealed decisions exist for this item yet.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.verification_results.map((r, i) => (
                    <ResultRow key={r.decision_id} result={r} index={i} />
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
