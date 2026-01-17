import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldExclamationIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useState } from 'react';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { fraudApi } from '../../services/api';
import { NetworkAlert, NetworkAlertSummary, MatchSeverity } from '../../types';

interface NetworkIntelligencePanelProps {
  checkItemId: string;
}

const severityConfig: Record<MatchSeverity, { color: string; bgColor: string; icon: React.ComponentType<{ className?: string }> }> = {
  low: { color: 'text-blue-700', bgColor: 'bg-blue-50 border-blue-200', icon: InformationCircleIcon },
  medium: { color: 'text-yellow-700', bgColor: 'bg-yellow-50 border-yellow-200', icon: ExclamationTriangleIcon },
  high: { color: 'text-red-700', bgColor: 'bg-red-50 border-red-200', icon: ShieldExclamationIcon },
};

function SeverityBadge({ severity }: { severity: MatchSeverity }) {
  const config = severityConfig[severity];
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
        config.bgColor,
        config.color
      )}
    >
      {severity}
    </span>
  );
}

interface AlertCardProps {
  alert: NetworkAlert;
  onDismiss: (alertId: string, reason: string) => void;
  isDismissing: boolean;
}

function AlertCard({ alert, onDismiss, isDismissing }: AlertCardProps) {
  const [showDismiss, setShowDismiss] = useState(false);
  const [dismissReason, setDismissReason] = useState('');
  const config = severityConfig[alert.severity];
  const Icon = config.icon;

  const handleDismiss = () => {
    if (!dismissReason.trim()) {
      toast.error('Please provide a reason for dismissing the alert');
      return;
    }
    onDismiss(alert.id, dismissReason);
    setShowDismiss(false);
    setDismissReason('');
  };

  return (
    <div className={clsx('p-3 rounded-lg border', config.bgColor)}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-2">
          <Icon className={clsx('h-5 w-5 flex-shrink-0 mt-0.5', config.color)} />
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className={clsx('text-sm font-medium', config.color)}>
                {alert.total_matches} Network Match{alert.total_matches !== 1 ? 'es' : ''}
              </span>
              <SeverityBadge severity={alert.severity} />
            </div>
            <p className="text-xs text-gray-600 mt-1">
              From {alert.distinct_institutions} institution{alert.distinct_institutions !== 1 ? 's' : ''}
              {alert.earliest_match_date && (
                <span>
                  {' '}| First seen: {new Date(alert.earliest_match_date).toLocaleDateString()}
                </span>
              )}
            </p>

            {/* Match Reasons */}
            <div className="mt-2 space-y-1">
              {alert.match_reasons.slice(0, 3).map((reason, idx) => (
                <div key={idx} className="text-xs">
                  <span className="font-medium text-gray-700">
                    {reason.indicator_type.replace(/_/g, ' ')}:
                  </span>{' '}
                  <span className="text-gray-600">
                    {reason.match_count} hit{reason.match_count !== 1 ? 's' : ''} for{' '}
                    {reason.fraud_types.slice(0, 2).join(', ')}
                    {reason.fraud_types.length > 2 && ` +${reason.fraud_types.length - 2} more`}
                  </span>
                </div>
              ))}
              {alert.match_reasons.length > 3 && (
                <p className="text-xs text-gray-500">
                  +{alert.match_reasons.length - 3} more match reason{alert.match_reasons.length - 3 !== 1 ? 's' : ''}
                </p>
              )}
            </div>
          </div>
        </div>

        {!alert.is_dismissed && (
          <button
            onClick={() => setShowDismiss(true)}
            className="text-gray-400 hover:text-gray-600 ml-2"
            title="Dismiss alert"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Dismiss Dialog */}
      {showDismiss && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Reason for dismissing
          </label>
          <textarea
            value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)}
            rows={2}
            className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            placeholder="Why are you dismissing this alert?"
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button
              onClick={() => {
                setShowDismiss(false);
                setDismissReason('');
              }}
              className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900"
            >
              Cancel
            </button>
            <button
              onClick={handleDismiss}
              disabled={isDismissing}
              className="px-2 py-1 text-xs font-medium text-white bg-gray-600 rounded hover:bg-gray-700 disabled:opacity-50"
            >
              {isDismissing ? 'Dismissing...' : 'Dismiss'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function NetworkIntelligencePanel({ checkItemId }: NetworkIntelligencePanelProps) {
  const queryClient = useQueryClient();

  // Fetch network alerts for this item
  const { data: alertSummary, isLoading, error } = useQuery<NetworkAlertSummary>({
    queryKey: ['networkAlerts', checkItemId],
    queryFn: () => fraudApi.getNetworkAlerts(checkItemId),
  });

  // Dismiss alert mutation
  const dismissAlert = useMutation({
    mutationFn: ({ alertId, reason }: { alertId: string; reason: string }) =>
      fraudApi.dismissAlert(alertId, reason),
    onSuccess: () => {
      toast.success('Alert dismissed');
      queryClient.invalidateQueries({ queryKey: ['networkAlerts', checkItemId] });
    },
    onError: (error: Error) => {
      toast.error(`Failed to dismiss alert: ${error.message}`);
    },
  });

  const handleDismiss = (alertId: string, reason: string) => {
    dismissAlert.mutate({ alertId, reason });
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-sm text-red-600">Failed to load network intelligence</p>
      </div>
    );
  }

  const activeAlerts = alertSummary?.alerts?.filter((a) => !a.is_dismissed) || [];

  return (
    <div className="bg-white rounded-lg border border-gray-200 h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center">
          <ShieldExclamationIcon className="h-4 w-4 mr-2 text-gray-400" />
          Network Intelligence
        </h3>
        {alertSummary?.highest_severity && (
          <SeverityBadge severity={alertSummary.highest_severity} />
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!alertSummary?.has_alerts || activeAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-6">
            <ShieldCheckIcon className="h-10 w-10 text-green-500 mb-2" />
            <p className="text-sm font-medium text-gray-900">No Network Matches</p>
            <p className="text-xs text-gray-500 mt-1">
              This check hasn't matched any fraud indicators across the network.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-xs text-gray-600 pb-2 border-b border-gray-100">
              Found {alertSummary.total_alerts} alert{alertSummary.total_alerts !== 1 ? 's' : ''} matching network fraud indicators
            </div>
            {activeAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onDismiss={handleDismiss}
                isDismissing={dismissAlert.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
