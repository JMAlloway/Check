import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeftIcon, DocumentArrowDownIcon, ShieldExclamationIcon } from '@heroicons/react/24/outline';
import { checkApi, auditApi, resolveImageUrl } from '../services/api';
import { CheckItem, CheckHistory, ROIRegion } from '../types';

// Image URL refresh interval (60 seconds - before 90s TTL expires)
const IMAGE_URL_REFRESH_INTERVAL = 60 * 1000;
import CheckImageViewer from '../components/check/CheckImageViewer';
import CheckContextPanel from '../components/check/CheckContextPanel';
import CheckHistoryPanel from '../components/check/CheckHistoryPanel';
import DecisionPanel from '../components/decision/DecisionPanel';
import NetworkIntelligencePanel from '../components/fraud/NetworkIntelligencePanel';
import FraudReportModal from '../components/fraud/FraudReportModal';
import { StatusBadge, RiskBadge, ItemTypeBadge } from '../components/common/StatusBadge';
import toast from 'react-hot-toast';

// Default ROI regions for check image
const defaultROIRegions: ROIRegion[] = [
  { id: 'amount', name: 'Amount Box', type: 'amount_box', x: 85, y: 25, width: 12, height: 10, color: '#ef4444' },
  { id: 'legal', name: 'Legal Line', type: 'legal_line', x: 10, y: 40, width: 70, height: 8, color: '#f97316' },
  { id: 'signature', name: 'Signature', type: 'signature', x: 60, y: 60, width: 35, height: 15, color: '#8b5cf6' },
  { id: 'micr', name: 'MICR Line', type: 'micr', x: 5, y: 85, width: 90, height: 10, color: '#3b82f6' },
  { id: 'payee', name: 'Payee', type: 'payee', x: 15, y: 25, width: 60, height: 8, color: '#22c55e' },
];

export default function CheckReviewPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const [comparisonItem, setComparisonItem] = useState<CheckHistory | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [showFraudModal, setShowFraudModal] = useState(false);

  const { data: item, isLoading, error } = useQuery<CheckItem>({
    queryKey: ['checkItem', itemId],
    queryFn: () => checkApi.getItem(itemId!),
    enabled: !!itemId,
    // Refetch every 60s to get fresh signed image URLs (TTL is 90s)
    // This ensures images stay accessible during long review sessions
    refetchInterval: IMAGE_URL_REFRESH_INTERVAL,
    // Only refetch when window is focused (save bandwidth when tab is hidden)
    refetchIntervalInBackground: false,
  });

  const [isGeneratingPacket, setIsGeneratingPacket] = useState(false);

  const handleGeneratePacket = async () => {
    if (!itemId) return;

    setIsGeneratingPacket(true);
    try {
      // Generate the packet
      const result = await auditApi.generatePacket({
        check_item_id: itemId,
        include_images: true,
        include_history: true,
        format: 'pdf',
      });

      // Download the PDF
      const filename = `audit_packet_${itemId.slice(0, 8)}.pdf`;
      await auditApi.downloadPacket(result.download_url, filename);

      toast.success('Audit packet downloaded');
    } catch (error) {
      console.error('Failed to generate packet:', error);
      toast.error('Failed to generate audit packet');
    } finally {
      setIsGeneratingPacket(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load check item</p>
        <Link to="/queue" className="text-primary-600 hover:underline mt-2 block">
          Return to Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            to="/queue"
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeftIcon className="h-5 w-5 mr-1" />
            Back to Queue
          </Link>
          <div className="h-6 w-px bg-gray-300" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Check Review: {item.account_number_masked}
            </h1>
            <div className="flex items-center space-x-2 mt-1">
              <ItemTypeBadge itemType={item.item_type} />
              <StatusBadge status={item.status} />
              <RiskBadge level={item.risk_level} />
              {item.requires_dual_control && (
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
                  Dual Control
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowFraudModal(true)}
            className="flex items-center px-3 py-2 text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100"
          >
            <ShieldExclamationIcon className="h-5 w-5 mr-1" />
            Report Fraud
          </button>
          <button
            onClick={handleGeneratePacket}
            disabled={isGeneratingPacket}
            className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGeneratingPacket ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 mr-1 border-b-2 border-gray-700"></div>
                Generating...
              </>
            ) : (
              <>
                <DocumentArrowDownIcon className="h-5 w-5 mr-1" />
                Audit Packet
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Content - Horizontal Layout */}
      <div className="flex flex-col gap-4" style={{ height: 'calc(100vh - 200px)' }}>
        {/* Top Row: Check Image Viewer (full width, optimized for horizontal checks) */}
        <div className="flex-shrink-0" style={{ height: showComparison ? '45%' : '50%' }}>
          <div className={`grid gap-4 h-full ${showComparison ? 'grid-cols-2' : 'grid-cols-1'}`}>
            <CheckImageViewer
              images={item.images}
              roiRegions={defaultROIRegions}
              showROI={true}
            />

            {/* Comparison View (side-by-side when active) */}
            {showComparison && comparisonItem && (
              <div className="bg-gray-900 rounded-lg h-full flex flex-col">
                <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex justify-between items-center">
                  <span className="text-white text-sm font-medium">
                    Historical Check - {new Date(comparisonItem.check_date).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => setShowComparison(false)}
                    className="text-gray-400 hover:text-white text-sm"
                  >
                    Close
                  </button>
                </div>
                <div className="flex-1 flex items-center justify-center">
                  {comparisonItem.front_image_url ? (
                    <img
                      src={resolveImageUrl(comparisonItem.front_image_url)}
                      alt="Historical check"
                      className="max-w-full max-h-full object-contain"
                    />
                  ) : (
                    <p className="text-gray-500">No image available</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bottom Row: Context Panels (horizontal layout) */}
        <div className="flex-1 min-h-0">
          <div className="grid grid-cols-4 gap-4 h-full">
            {/* Context Panel */}
            <div className="overflow-hidden">
              <CheckContextPanel item={item} />
            </div>

            {/* History Panel */}
            <div className="overflow-hidden">
              <CheckHistoryPanel
                itemId={item.id}
                currentAmount={item.amount}
                onSelectComparison={(historyItem) => {
                  setComparisonItem(historyItem);
                  setShowComparison(true);
                }}
              />
            </div>

            {/* Network Intelligence Panel */}
            <div className="overflow-hidden">
              <NetworkIntelligencePanel checkItemId={item.id} />
            </div>

            {/* Decision Panel */}
            <div className="overflow-hidden">
              <DecisionPanel item={item} />
            </div>
          </div>
        </div>
      </div>

      {/* Fraud Report Modal */}
      <FraudReportModal
        isOpen={showFraudModal}
        onClose={() => setShowFraudModal(false)}
        item={item}
      />
    </div>
  );
}
