import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { XMarkIcon, ExclamationTriangleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { fraudApi } from '../../services/api';
import {
  CheckItem,
  FraudType,
  FraudChannel,
  SharingLevel,
  FraudEventCreate,
  PIIDetectionResult,
} from '../../types';

interface FraudReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: CheckItem;
}

const FRAUD_TYPES: { value: FraudType; label: string }[] = [
  { value: 'check_kiting', label: 'Check Kiting' },
  { value: 'counterfeit_check', label: 'Counterfeit Check' },
  { value: 'forged_signature', label: 'Forged Signature' },
  { value: 'altered_check', label: 'Altered Check' },
  { value: 'account_takeover', label: 'Account Takeover' },
  { value: 'identity_theft', label: 'Identity Theft' },
  { value: 'first_party_fraud', label: 'First Party Fraud' },
  { value: 'synthetic_identity', label: 'Synthetic Identity' },
  { value: 'duplicate_deposit', label: 'Duplicate Deposit' },
  { value: 'unauthorized_endorsement', label: 'Unauthorized Endorsement' },
  { value: 'payee_alteration', label: 'Payee Alteration' },
  { value: 'amount_alteration', label: 'Amount Alteration' },
  { value: 'fictitious_payee', label: 'Fictitious Payee' },
  { value: 'other', label: 'Other' },
];

const CHANNELS: { value: FraudChannel; label: string }[] = [
  { value: 'branch', label: 'Branch' },
  { value: 'atm', label: 'ATM' },
  { value: 'mobile', label: 'Mobile Deposit' },
  { value: 'rdc', label: 'Remote Deposit Capture' },
  { value: 'mail', label: 'Mail' },
  { value: 'online', label: 'Online Banking' },
  { value: 'other', label: 'Other' },
];

const SHARING_LEVELS: { value: SharingLevel; label: string; description: string }[] = [
  { value: 0, label: 'Private', description: 'Keep this event internal only - no network sharing' },
  { value: 1, label: 'Aggregate Only', description: 'Share anonymized data for trend analysis' },
  { value: 2, label: 'Network Match', description: 'Enable cross-institution matching (recommended)' },
];

export default function FraudReportModal({ isOpen, onClose, item }: FraudReportModalProps) {
  const queryClient = useQueryClient();

  // Form state
  const [fraudType, setFraudType] = useState<FraudType>('other');
  const [channel, setChannel] = useState<FraudChannel>('branch');
  const [confidence, setConfidence] = useState(80);
  const [narrativePrivate, setNarrativePrivate] = useState('');
  const [narrativeShareable, setNarrativeShareable] = useState('');
  const [sharingLevel, setSharingLevel] = useState<SharingLevel>(2);
  const [confirmNoPII, setConfirmNoPII] = useState(false);

  // PII check result
  const [piiResult, setPiiResult] = useState<PIIDetectionResult | null>(null);
  const [isCheckingPII, setIsCheckingPII] = useState(false);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFraudType('other');
      setChannel('branch');
      setConfidence(80);
      setNarrativePrivate('');
      setNarrativeShareable('');
      setSharingLevel(2);
      setConfirmNoPII(false);
      setPiiResult(null);
    }
  }, [isOpen]);

  // Check PII when shareable narrative changes
  useEffect(() => {
    if (!narrativeShareable.trim() || sharingLevel < 2) {
      setPiiResult(null);
      return;
    }

    const checkPII = async () => {
      setIsCheckingPII(true);
      try {
        const result = await fraudApi.checkPII(narrativeShareable, false);
        setPiiResult(result);
      } catch {
        // Silently fail - don't block submission
        setPiiResult(null);
      } finally {
        setIsCheckingPII(false);
      }
    };

    const timer = setTimeout(checkPII, 500);
    return () => clearTimeout(timer);
  }, [narrativeShareable, sharingLevel]);

  // Create event mutation
  const createEvent = useMutation({
    mutationFn: fraudApi.createEvent,
    onSuccess: () => {
      toast.success('Fraud event created successfully');
      queryClient.invalidateQueries({ queryKey: ['checkItem', item.id] });
      queryClient.invalidateQueries({ queryKey: ['fraudEvents'] });
      onClose();
    },
    onError: (error: Error) => {
      toast.error(`Failed to create fraud event: ${error.message}`);
    },
  });

  const handleSubmit = () => {
    // Validation
    if (sharingLevel >= 2 && narrativeShareable.trim() && !confirmNoPII) {
      toast.error('Please confirm the shareable narrative contains no PII');
      return;
    }

    if (piiResult?.has_potential_pii && sharingLevel >= 2) {
      toast.error('Please remove potential PII from the shareable narrative before submitting');
      return;
    }

    const data: FraudEventCreate = {
      check_item_id: item.id,
      event_date: new Date().toISOString(),
      amount: item.amount,
      fraud_type: fraudType,
      channel: channel,
      confidence: confidence / 100, // Convert to 0-1 range
      narrative_private: narrativePrivate.trim() || undefined,
      narrative_shareable: narrativeShareable.trim() || undefined,
      sharing_level: sharingLevel,
    };

    createEvent.mutate(data);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <ShieldCheckIcon className="h-6 w-6 text-red-600" />
            <h2 className="text-lg font-semibold text-gray-900">Report Fraud Event</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Pre-filled Information */}
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Check Information</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Account:</span>{' '}
              <span className="font-medium">{item.account_number_masked}</span>
            </div>
            <div>
              <span className="text-gray-500">Amount:</span>{' '}
              <span className="font-medium">${item.amount.toLocaleString()}</span>
            </div>
            {item.check_number && (
              <div>
                <span className="text-gray-500">Check #:</span>{' '}
                <span className="font-medium">{item.check_number}</span>
              </div>
            )}
            {item.payee_name && (
              <div>
                <span className="text-gray-500">Payee:</span>{' '}
                <span className="font-medium">{item.payee_name}</span>
              </div>
            )}
          </div>
        </div>

        {/* Form */}
        <div className="px-6 py-4 space-y-4">
          {/* Fraud Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Fraud Type <span className="text-red-500">*</span>
            </label>
            <select
              value={fraudType}
              onChange={(e) => setFraudType(e.target.value as FraudType)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            >
              {FRAUD_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Channel */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Channel <span className="text-red-500">*</span>
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as FraudChannel)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            >
              {CHANNELS.map((ch) => (
                <option key={ch.value} value={ch.value}>
                  {ch.label}
                </option>
              ))}
            </select>
          </div>

          {/* Confidence */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confidence Level: {confidence}%
            </label>
            <input
              type="range"
              min="10"
              max="100"
              step="5"
              value={confidence}
              onChange={(e) => setConfidence(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>

          {/* Private Narrative */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Internal Notes (Private)
            </label>
            <textarea
              value={narrativePrivate}
              onChange={(e) => setNarrativePrivate(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              placeholder="Internal details about the fraud event (not shared externally)..."
            />
          </div>

          {/* Shareable Narrative */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shareable Description (Network-visible)
            </label>
            <textarea
              value={narrativeShareable}
              onChange={(e) => setNarrativeShareable(e.target.value)}
              rows={3}
              className={clsx(
                'w-full rounded-lg border px-3 py-2 text-sm focus:ring-1',
                piiResult?.has_potential_pii
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500'
              )}
              placeholder="Description that may be shared with the network (NO PII)..."
            />
            {isCheckingPII && (
              <p className="text-xs text-gray-500 mt-1">Checking for PII...</p>
            )}
            {piiResult?.has_potential_pii && (
              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start space-x-2">
                  <ExclamationTriangleIcon className="h-5 w-5 text-red-600 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-red-800">Potential PII Detected</p>
                    <ul className="text-xs text-red-700 mt-1 list-disc list-inside">
                      {piiResult.warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sharing Level */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sharing Level <span className="text-red-500">*</span>
            </label>
            <div className="space-y-2">
              {SHARING_LEVELS.map((level) => (
                <label
                  key={level.value}
                  className={clsx(
                    'flex items-start p-3 rounded-lg border cursor-pointer transition-colors',
                    sharingLevel === level.value
                      ? 'bg-primary-50 border-primary-300'
                      : 'border-gray-200 hover:bg-gray-50'
                  )}
                >
                  <input
                    type="radio"
                    name="sharingLevel"
                    value={level.value}
                    checked={sharingLevel === level.value}
                    onChange={() => setSharingLevel(level.value)}
                    className="mt-1 text-primary-600"
                  />
                  <div className="ml-3">
                    <div className="text-sm font-medium text-gray-900">{level.label}</div>
                    <div className="text-xs text-gray-500">{level.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* PII Confirmation */}
          {sharingLevel >= 2 && narrativeShareable.trim() && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <label className="flex items-start cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmNoPII}
                  onChange={(e) => setConfirmNoPII(e.target.checked)}
                  className="mt-1 rounded border-gray-300 text-primary-600"
                />
                <span className="ml-2 text-sm text-yellow-800">
                  I confirm the shareable narrative contains no Personally Identifiable Information
                  (PII) such as names, addresses, SSN, account numbers, or other sensitive data.
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={createEvent.isPending || (piiResult?.has_potential_pii && sharingLevel >= 2)}
            className={clsx(
              'px-4 py-2 text-sm font-medium text-white rounded-lg',
              createEvent.isPending || (piiResult?.has_potential_pii && sharingLevel >= 2)
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-red-600 hover:bg-red-700'
            )}
          >
            {createEvent.isPending ? 'Creating...' : 'Report Fraud Event'}
          </button>
        </div>
      </div>
    </div>
  );
}
