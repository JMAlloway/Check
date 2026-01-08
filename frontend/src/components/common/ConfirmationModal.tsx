import { ExclamationTriangleIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import clsx from 'clsx';

type ActionType = 'approve' | 'reject' | 'return' | 'escalate' | 'default';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  actionType?: ActionType;
  isPending?: boolean;
  details?: {
    label: string;
    value: string;
  }[];
}

const ACTION_STYLES: Record<ActionType, { icon: typeof CheckCircleIcon; color: string; buttonClass: string }> = {
  approve: {
    icon: CheckCircleIcon,
    color: 'text-green-600',
    buttonClass: 'bg-green-600 hover:bg-green-700 focus:ring-green-500',
  },
  reject: {
    icon: XCircleIcon,
    color: 'text-red-600',
    buttonClass: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
  },
  return: {
    icon: ExclamationTriangleIcon,
    color: 'text-orange-600',
    buttonClass: 'bg-orange-600 hover:bg-orange-700 focus:ring-orange-500',
  },
  escalate: {
    icon: ExclamationTriangleIcon,
    color: 'text-purple-600',
    buttonClass: 'bg-purple-600 hover:bg-purple-700 focus:ring-purple-500',
  },
  default: {
    icon: ExclamationTriangleIcon,
    color: 'text-primary-600',
    buttonClass: 'bg-primary-600 hover:bg-primary-700 focus:ring-primary-500',
  },
};

export default function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  actionType = 'default',
  isPending = false,
  details,
}: ConfirmationModalProps) {
  if (!isOpen) return null;

  const style = ACTION_STYLES[actionType];
  const Icon = style.icon;

  const handleConfirm = () => {
    if (!isPending) {
      onConfirm();
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && !isPending) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirmation-title"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center space-x-3 px-6 py-4 border-b border-gray-200">
          <Icon className={clsx('h-6 w-6', style.color)} />
          <h2 id="confirmation-title" className="text-lg font-semibold text-gray-900">
            {title}
          </h2>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          <p className="text-sm text-gray-600">{message}</p>

          {/* Details */}
          {details && details.length > 0 && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <dl className="space-y-2">
                {details.map((detail, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <dt className="text-gray-500">{detail.label}:</dt>
                    <dd className="font-medium text-gray-900">{detail.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Warning for final actions */}
          {(actionType === 'approve' || actionType === 'reject' || actionType === 'return') && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                <strong>This action is final.</strong> Once submitted, this decision cannot be
                easily reversed without supervisor approval.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            disabled={isPending}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-lg border transition-colors',
              isPending
                ? 'text-gray-400 border-gray-200 cursor-not-allowed'
                : 'text-gray-700 bg-white border-gray-300 hover:bg-gray-50'
            )}
          >
            {cancelText}
          </button>
          <button
            onClick={handleConfirm}
            disabled={isPending}
            className={clsx(
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
              isPending ? 'bg-gray-400 cursor-not-allowed' : style.buttonClass
            )}
          >
            {isPending ? (
              <span className="flex items-center">
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Processing...
              </span>
            ) : (
              confirmText
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
