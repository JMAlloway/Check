import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { CheckItem, ReasonCode, DecisionAction } from '../../types';
import { decisionApi } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
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

export default function DecisionPanel({ item, onDecisionMade }: DecisionPanelProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();

  const [selectedAction, setSelectedAction] = useState<DecisionAction | null>(null);
  const [selectedReasonCodes, setSelectedReasonCodes] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [acknowledgeAI, setAcknowledgeAI] = useState(false);

  const canReview = hasPermission('check_item', 'review');
  const canApprove = hasPermission('check_item', 'approve');

  // Determine which actions to show based on status and permissions
  const isAwaitingApproval = item.status === 'pending_approval';
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
      toast.success('Decision submitted successfully');
      queryClient.invalidateQueries({ queryKey: ['checkItem', item.id] });
      queryClient.invalidateQueries({ queryKey: ['checkItems'] });
      onDecisionMade?.();
      navigate('/queue');
    },
    onError: (error: Error) => {
      toast.error(`Failed to submit decision: ${error.message}`);
    },
  });

  const handleSubmit = () => {
    if (!selectedAction) {
      toast.error('Please select an action');
      return;
    }

    // Check if reason codes are required
    if (selectedAction !== 'approve' && selectedReasonCodes.length === 0) {
      toast.error('Please select at least one reason code');
      return;
    }

    // Check if notes are required for certain reason codes
    const requiresNotes = reasonCodes?.some(
      (rc: ReasonCode) => selectedReasonCodes.includes(rc.id) && rc.requires_notes
    );
    if (requiresNotes && !notes.trim()) {
      toast.error('Notes are required for the selected reason code(s)');
      return;
    }

    // Check AI acknowledgment
    if (item.ai_flags.length > 0 && !acknowledgeAI) {
      toast.error('Please acknowledge the AI flags');
      return;
    }

    createDecision.mutate({
      check_item_id: item.id,
      decision_type: decisionType,
      action: selectedAction,
      reason_code_ids: selectedReasonCodes,
      notes: notes.trim() || undefined,
      ai_assisted: item.ai_flags.length > 0,
    });
  };

  const toggleReasonCode = (codeId: string) => {
    setSelectedReasonCodes((prev) =>
      prev.includes(codeId) ? prev.filter((id) => id !== codeId) : [...prev, codeId]
    );
  };

  if (!canReview && !canApprove) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-gray-500 text-center">
          You do not have permission to make decisions on this item.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        {isAwaitingApproval ? 'Final Decision' : 'Review Recommendation'}
      </h3>

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
              }}
              className={clsx(
                'px-4 py-2 text-sm font-medium rounded-lg border transition-colors',
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

      {/* Reason Codes */}
      {selectedAction && selectedAction !== 'approve' && reasonCodes && (
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
                  selectedReasonCodes.includes(code.id)
                    ? 'bg-primary-50 border border-primary-200'
                    : 'hover:bg-gray-50 border border-transparent'
                )}
              >
                <input
                  type="checkbox"
                  checked={selectedReasonCodes.includes(code.id)}
                  onChange={() => toggleReasonCode(code.id)}
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
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          placeholder="Add any additional notes..."
        />
      </div>

      {/* AI Acknowledgment */}
      {item.ai_flags.length > 0 && (
        <div className="mb-4">
          <label className="flex items-start cursor-pointer">
            <input
              type="checkbox"
              checked={acknowledgeAI}
              onChange={(e) => setAcknowledgeAI(e.target.checked)}
              className="mt-1 rounded border-gray-300 text-primary-600"
            />
            <span className="ml-2 text-sm text-gray-600">
              I have reviewed the {item.ai_flags.length} AI flag(s) for this item
            </span>
          </label>
        </div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={createDecision.isPending}
        className={clsx(
          'w-full py-2 px-4 rounded-lg font-medium text-white transition-colors',
          createDecision.isPending
            ? 'bg-gray-400 cursor-not-allowed'
            : 'bg-primary-600 hover:bg-primary-700'
        )}
      >
        {createDecision.isPending ? 'Submitting...' : 'Submit Decision'}
      </button>
    </div>
  );
}
