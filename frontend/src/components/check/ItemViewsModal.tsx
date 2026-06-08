import { useQuery } from '@tanstack/react-query';
import { EyeIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { auditApi } from '../../services/api';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import type { ItemView } from '../../types';

interface ItemViewsModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemId: string;
}

function flags(v: ItemView): string {
  const f: string[] = [];
  if (v.front_image_viewed) f.push('front');
  if (v.back_image_viewed) f.push('back');
  if (v.zoom_used) f.push('zoom');
  if (v.magnifier_used) f.push('magnifier');
  if (v.history_compared) f.push('history');
  if (v.ai_assists_viewed) f.push('risk signals');
  return f.join(' · ') || 'no interactions recorded';
}

export default function ItemViewsModal({ isOpen, onClose, itemId }: ItemViewsModalProps) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['item-views', itemId],
    queryFn: () => auditApi.getItemViews(itemId),
    enabled: isOpen,
  });
  const trapRef = useFocusTrap<HTMLDivElement>(isOpen, onClose);

  if (!isOpen) return null;

  const views = data ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Item view history"
    >
      <div ref={trapRef} className="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
            <EyeIcon className="h-5 w-5 text-primary-600" aria-hidden="true" />
            Who viewed this check
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
          {isLoading && <p className="py-6 text-center text-sm text-gray-500">Loading view history…</p>}
          {isError && !isLoading && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
              <p className="text-sm text-red-800">Could not load view history.</p>
              <button
                onClick={() => refetch()}
                className="mt-2 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          )}
          {!isLoading && !isError && views.length === 0 && (
            <p className="py-6 text-center text-sm text-gray-500">No recorded views for this item.</p>
          )}
          {views.length > 0 && (
            <ul className="space-y-2">
              {views.map((v) => (
                <li key={v.id} className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-gray-900">
                      {v.username ?? v.user_id.slice(0, 8)}
                    </span>
                    <span className="text-xs text-gray-500">
                      {v.duration_seconds != null ? `${v.duration_seconds}s` : '—'}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-gray-600">
                    {new Date(v.view_started_at).toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">{flags(v)}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
