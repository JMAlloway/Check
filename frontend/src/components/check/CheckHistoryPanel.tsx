import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckHistory } from '../../types';
import { checkApi, resolveImageUrl } from '../../services/api';
import { formatDate } from '../../utils/date';
import clsx from 'clsx';

interface CheckHistoryPanelProps {
  itemId: string;
  currentAmount: number;
  onSelectComparison?: (historyItem: CheckHistory) => void;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

/**
 * Prior checks from the same account as a horizontal filmstrip of thumbnails.
 * Lives directly under the image viewer so clicking a card opens the
 * side-by-side comparison right where the reviewer is already looking -
 * no scrolling between the history list and the comparison result.
 */
export default function CheckHistoryPanel({
  itemId,
  currentAmount,
  onSelectComparison,
}: CheckHistoryPanelProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: history, isLoading } = useQuery({
    queryKey: ['checkHistory', itemId],
    queryFn: () => checkApi.getHistory(itemId, 10),
  });

  const handleSelect = (item: CheckHistory) => {
    setSelectedId(item.id);
    onSelectComparison?.(item);
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <div className="animate-pulse flex gap-3">
          <div className="h-20 w-40 bg-gray-200 rounded"></div>
          <div className="h-20 w-40 bg-gray-200 rounded"></div>
          <div className="h-20 w-40 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (!history || history.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-500">
        <span className="font-medium text-gray-700">Check History</span>
        <span> — no prior checks on file for this account</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900">
          Check History
          <span className="ml-2 font-normal text-gray-500">
            {history.length} prior check{history.length !== 1 ? 's' : ''} — click to compare
          </span>
        </h3>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {history.map((item: CheckHistory) => {
          const amountDiff = Math.abs(item.amount - currentAmount);
          const isSimilar = amountDiff / currentAmount < 0.2;
          const selected = selectedId === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleSelect(item)}
              className={clsx(
                'shrink-0 w-44 rounded-lg border text-left transition-colors overflow-hidden',
                selected
                  ? 'border-primary-500 ring-1 ring-primary-500'
                  : 'border-gray-200 hover:border-gray-400'
              )}
            >
              <div className="h-16 bg-gray-100 flex items-center justify-center overflow-hidden">
                {item.front_image_url ? (
                  <img
                    src={resolveImageUrl(item.front_image_url)}
                    alt={`Check from ${formatDate(item.check_date)}`}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <span className="text-xs text-gray-400">No image</span>
                )}
              </div>
              <div className="px-2 py-1.5">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-sm font-medium text-gray-900">
                    {formatCurrency(item.amount)}
                  </span>
                  <span
                    className={clsx(
                      'text-[10px] px-1.5 py-0.5 rounded capitalize whitespace-nowrap',
                      item.status === 'cleared'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    )}
                  >
                    {item.status}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-1 mt-0.5">
                  <span className="text-xs text-gray-500">{formatDate(item.check_date)}</span>
                  {isSimilar && (
                    <span className="text-[10px] text-green-600 bg-green-100 px-1 py-0.5 rounded">
                      Similar
                    </span>
                  )}
                </div>
                {item.return_reason && (
                  <div className="text-[10px] text-red-600 truncate">{item.return_reason}</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
