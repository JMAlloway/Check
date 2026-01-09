import { useState, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { LockClosedIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { CheckItem, ReasonCode, DecisionAction } from '../../types';
import { decisionApi } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
import ConfirmationModal from '../common/ConfirmationModal';
import clsx from 'clsx';

interface DecisionPanelProps {
  item: CheckItem;
  onDecisionMade?: () => void;
}

const reviewActions: { action: DecisionAction; label: string; color: string }[] = [
  { action: 'approve', label: 'Recommend Approve', color: 'green' },
  { action: 'return', label: 'Recommend Return', color: 'orange' },
  { action: 'reject', label: 'Recommend Reject', color: 'red' },
  { action: 'escalate', label: 'Escalate', color: 'purple' },
  { action: 'needs_more_info', label: 'Need More Info', color: 'blue' },
];

const approvalActions: { action: DecisionAction; label: string; color: string }[] = [
  { action: 'approve', label: 'Approve', color: 'green' },
  { action: 'return', label: 'Return', color: 'orange' },
  { action: 'reject', label: 'Reject', color: 'red' },
];

// Actions that require confirmation modal (final/high-impact)
const FINAL_ACTIONS: DecisionAction[] = ['approve', 'return', 'reject'];

// Debounce delay in ms to prevent double-clicks
const SUBMIT_DEBOUNCE_MS = 1000;

// Terminal statuses where the item is locked
const LOCKED_STATUSES = ['approved', 'rejected', 'returned', 'closed'];

export default function DecisionPanel({ item, onDecisionMade }: DecisionPanelProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();

  const [selectedAction, setSelectedAction] = useState<DecisionAction | null>(null);
  const [selectedReasonCodes, setSelectedReasonCodes] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [acknowledgeAI, setAcknowledgeAI] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Double-click protection
  const lastSubmitTime = useRef<number>(0);
  const [isDebouncing, setIsDebouncing] = useState(false);

  const canReview = hasPermission('check_item', 'review');
  const canApprove = hasPermission('check_item', 'approve');

  // Check if item is locked (terminal state)
  const isLocked = LOCKED_STATUSES.includes(item.status);

  // Determine which actions to show based on status and permissions
  const isAwaitingApproval = item.status === 'pending_approval' || item.status === 'pending_dual_control';
  const actions = isAwaitingApproval && canApprove ? approvalActions : reviewActions;
  const decisionType = isAwaitingApproval && canApprove ? 'approval_decision' : 'review_recommendation';

  // Fetch reason codes
  const { data: reasonCodes } = useQuery({
    queryKey: ['reasonCodes', selectedAction],
    queryFn: () => decisionApi.getReasonCodes(undefined, selectedAction || undefined),
    enabled: !!selectedAction && selectedAction !== 'approve',
  });

  // Create decision mutation
  const createDecision = useMutation({
    mutationFn: decisionApi.createDecision,
    onSuccess: () => {
      toast.success('Decision submitted successfully', {
        duration: 4000,
        icon: '✓',
      });
      queryClient.invalidateQueries({ queryKey: ['checkItem', item.id] });
      queryClient.invalidateQueries({ queryKey: ['checkItems'] });
      setShowConfirmation(false);
      onDecisionMade?.();
      navigate('/queue');
    },
    onError: (error: Error) => {
      setShowConfirmation(false);
      toast.error(`Decision failed: ${error.message}`, {
        duration: 6000,
      });
      // Also show inline error for visibility
      setValidationErrors([error.message]);
    },
    onSettled: () => {
      setIsDebouncing(false);
    },
  });

  const validateForm = useCallback((): string[] => {
    const errors: string[] = [];

    if (!selectedAction) {
      errors.push('Please select an action');
    }

    // Check if reason codes are required (only for reject/return)
    if (selectedAction && (selectedAction === 'reject' || selectedAction === 'return') && selectedReasonCodes.length === 0) {
      errors.push('Please select at least one reason code');
    }

    // Check if notes are required for certain reason codes
    const requiresNotes = reasonCodes?.some(
      (rc: ReasonCode) => selectedReasonCodes.includes(rc.id) && rc.requires_notes
    );
    if (requiresNotes && !notes.trim()) {
      errors.push('Notes are required for the selected reason code(s)');
    }

    // Check AI acknowledgment
    if (item.ai_flags.length > 0 && !acknowledgeAI) {
      errors.push('Please acknowledge the AI flags before submitting');
    }

    return errors;
  }, [selectedAction, selectedReasonCodes, reasonCodes, notes, item.ai_flags.length, acknowledgeAI]);

  const handleSubmitClick = useCallback(() => {
    // Double-click protection
    const now = Date.now();
    if (now - lastSubmitTime.current < SUBMIT_DEBOUNCE_MS) {
      return;
    }

    // Clear previous errors
    setValidationErrors([]);

    // Validate
    const errors = validateForm();
    if (errors.length > 0) {
      setValidationErrors(errors);
      errors.forEach((err) => toast.error(err));
      return;
    }

    // For final actions, show confirmation modal
    if (selectedAction && FINAL_ACTIONS.includes(selectedAction)) {
      setShowConfirmation(true);
    } else {
      // For non-final actions (escalate, needs_more_info), submit directly
      handleConfirmedSubmit();
    }
  }, [validateForm, selectedAction]);

  const handleConfirmedSubmit = useCallback(() => {
    if (!selectedAction) return;

    // Double-click protection
    const now = Date.now();
    if (now - lastSubmitTime.current < SUBMIT_DEBOUNCE_MS) {
      return;
    }
    lastSubmitTime.current = now;
    setIsDebouncing(true);

    createDecision.mutate({
      check_item_id: item.id,
      decision_type: decisionType,
      action: selectedAction,
      reason_code_ids: selectedReasonCodes,
      notes: notes.trim() || undefined,
      ai_assisted: item.ai_flags.length > 0,
    });
  }, [selectedAction, item.id, item.ai_flags, decisionType, selectedReasonCodes, notes, createDecision]);

  const toggleReasonCode = (codeId: string) => {
    setSelectedReasonCodes((prev) =>
      prev.includes(codeId) ? prev.filter((id) => id !== codeId) : [...prev, codeId]
    );
    // Clear validation errors when user makes changes
    setValidationErrors([]);
  };

  const getConfirmationDetails = () => {
    const details = [
      { label: 'Account', value: item.account_number_masked },
      { label: 'Amount', value: `$${item.amount.toLocaleString()}` },
      { label: 'Action', value: selectedAction?.toUpperCase() || '' },
    ];

    if (selectedReasonCodes.length > 0 && reasonCodes) {
      const codes = reasonCodes
        .filter((rc: ReasonCode) => selectedReasonCodes.includes(rc.id))
        .map((rc: ReasonCode) => rc.code)
        .join(', ');
      details.push({ label: 'Reason(s)', value: codes });
    }

    return details;
  };

  const getConfirmationMessage = () => {
    if (isAwaitingApproval) {
      return `You are about to ${selectedAction} this check item. This is a final decision under dual control and will be recorded in the audit log.`;
    }
    if (item.requires_dual_control) {
      return `Your ${selectedAction} recommendation will be sent for final approval by a second reviewer.`;
    }
    return `You are about to ${selectedAction} this check item. This action will be recorded in the audit log.`;
  };

  // Show locked state
  if (isLocked) {
    return (
      <div className="bg-gray-50 rounded-lg border border-gray-300 p-4">
        <div className="flex items-center space-x-3 text-gray-600">
          <LockClosedIcon className="h-6 w-6" />
          <div>
            <h3 className="text-lg font-semibold">Decision Locked</h3>
            <p className="text-sm text-gray-500">
              This item has been {item.status}. No further decisions can be made.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!canReview && !canApprove) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-gray-500 text-center">
          You do not have permission to make decisions on this item.
        </p>
      </div>
    );
  }

  const isSubmitting = createDecision.isPending || isDebouncing;

  return (
    <>
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {isAwaitingApproval ? 'Final Decision' : 'Review Recommendation'}
        </h3>

        {/* Validation Errors Display */}
        {validationErrors.length > 0 && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start space-x-2">
              <ExclamationCircleIcon className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Please fix the following:</p>
                <ul className="text-sm text-red-700 mt-1 list-disc list-inside">
                  {validationErrors.map((error, idx) => (
                    <li key={idx}>{error}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Dual Control Warning */}
        {item.requires_dual_control && !isAwaitingApproval && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              <strong>Dual Control Required:</strong> This item requires a second approver.
              Your recommendation will be sent for final approval.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Action
          </label>
          <div className="grid grid-cols-2 gap-2">
            {actions.map(({ action, label, color }) => (
              <button
                key={action}
                onClick={() => {
                  setSelectedAction(action);
                  setSelectedReasonCodes([]);
                  setValidationErrors([]);
                }}
                disabled={isSubmitting}
                className={clsx(
                  'px-4 py-2 text-sm font-medium rounded-lg border transition-colors',
                  isSubmitting && 'opacity-50 cursor-not-allowed',
                  selectedAction === action
                    ? `bg-${color}-100 border-${color}-500 text-${color}-700`
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50',
                  color === 'green' && selectedAction === action && 'bg-green-100 border-green-500 text-green-700',
                  color === 'orange' && selectedAction === action && 'bg-orange-100 border-orange-500 text-orange-700',
                  color === 'red' && selectedAction === action && 'bg-red-100 border-red-500 text-red-700',
                  color === 'purple' && selectedAction === action && 'bg-purple-100 border-purple-500 text-purple-700',
                  color === 'blue' && selectedAction === action && 'bg-blue-100 border-blue-500 text-blue-700'
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Reason Codes - only required for reject/return actions */}
        {selectedAction && (selectedAction === 'reject' || selectedAction === 'return') && reasonCodes && (
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reason Code(s) <span className="text-red-500">*</span>
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {reasonCodes.map((code: ReasonCode) => (
                <label
                  key={code.id}
                  className={clsx(
                    'flex items-start p-2 rounded cursor-pointer transition-colors',
                    isSubmitting && 'opacity-50 pointer-events-none',
                    selectedReasonCodes.includes(code.id)
                      ? 'bg-primary-50 border border-primary-200'
                      : 'hover:bg-gray-50 border border-transparent'
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedReasonCodes.includes(code.id)}
                    onChange={() => toggleReasonCode(code.id)}
                    disabled={isSubmitting}
                    className="mt-1 rounded border-gray-300 text-primary-600"
                  />
                  <div className="ml-2">
                    <div className="text-sm font-medium text-gray-900">{code.code}</div>
                    <div className="text-xs text-gray-500">{code.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Notes
            {reasonCodes?.some(
              (rc: ReasonCode) => selectedReasonCodes.includes(rc.id) && rc.requires_notes
            ) && <span className="text-red-500"> *</span>}
          </label>
          <textarea
            value={notes}
            onChange={(e) => {
              setNotes(e.target.value);
              setValidationErrors([]);
            }}
            rows={3}
            disabled={isSubmitting}
            className={clsx(
              'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500',
              isSubmitting && 'opacity-50 cursor-not-allowed'
            )}
            placeholder="Add any additional notes..."
          />
        </div>

        {/* AI Acknowledgment */}
        {item.ai_flags.length > 0 && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <label className="flex items-start cursor-pointer">
              <input
                type="checkbox"
                checked={acknowledgeAI}
                onChange={(e) => {
                  setAcknowledgeAI(e.target.checked);
                  setValidationErrors([]);
                }}
                disabled={isSubmitting}
                className="mt-1 rounded border-gray-300 text-primary-600"
              />
              <span className="ml-2 text-sm text-blue-800">
                <strong>Advisory:</strong> I have reviewed the {item.ai_flags.length} AI-generated flag(s)
                for this item. I understand AI analysis is advisory only and the final decision is mine.
              </span>
            </label>
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={handleSubmitClick}
          disabled={isSubmitting}
          className={clsx(
            'w-full py-2 px-4 rounded-lg font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500',
            isSubmitting
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-primary-600 hover:bg-primary-700'
          )}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center">
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
            'Submit Decision'
          )}
        </button>
      </div>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={showConfirmation}
        onClose={() => setShowConfirmation(false)}
        onConfirm={handleConfirmedSubmit}
        title={`Confirm ${selectedAction?.charAt(0).toUpperCase()}${selectedAction?.slice(1)}`}
        message={getConfirmationMessage()}
        confirmText={`${selectedAction?.charAt(0).toUpperCase()}${selectedAction?.slice(1)} Decision`}
        cancelText="Go Back"
        actionType={selectedAction as 'approve' | 'reject' | 'return' | 'default'}
        isPending={isSubmitting}
        details={getConfirmationDetails()}
      />
    </>
  );
}
