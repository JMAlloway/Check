import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckHistory } from '../../types';
import { checkApi, resolveImageUrl } from '../../services/api';
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
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full overflow-hidden flex flex-col">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Check History</h3>

      {!history || history.length === 0 ? (
        <div className="text-gray-500 text-sm text-center py-8">
          No check history available for this account
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto flex-1">
          {history.map((item: CheckHistory) => {
            const amountDiff = Math.abs(item.amount - currentAmount);
            const isSimilar = amountDiff / currentAmount < 0.2;

            return (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                className={clsx(
                  'p-3 rounded-lg border cursor-pointer transition-colors',
                  selectedId === item.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                )}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-medium text-gray-900">
                      {formatCurrency(item.amount)}
                      {isSimilar && (
                        <span className="ml-2 text-xs text-green-600 bg-green-100 px-1.5 py-0.5 rounded">
                          Similar
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(item.check_date).toLocaleDateString()}
                    </div>
                    {item.payee_name && (
                      <div className="text-sm text-gray-600 truncate">
                        {item.payee_name}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <span
                      className={clsx(
                        'text-xs px-2 py-1 rounded',
                        item.status === 'cleared'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      )}
                    >
                      {item.status}
                    </span>
                    {item.return_reason && (
                      <div className="text-xs text-red-600 mt-1">
                        {item.return_reason}
                      </div>
                    )}
                  </div>
                </div>

                {selectedId === item.id && item.front_image_url && (
                  <div className="mt-3 border-t pt-3">
                    <img
                      src={resolveImageUrl(item.front_image_url)}
                      alt="Historical check"
                      className="w-full rounded border"
                    />
                    <button
                      className="mt-2 w-full text-sm text-primary-600 hover:text-primary-700 font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectComparison?.(item);
                      }}
                    >
                      Compare Side-by-Side
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
