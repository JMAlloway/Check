import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftIcon,
  DocumentArrowDownIcon,
  ShieldExclamationIcon,
  ShieldCheckIcon,
  UserPlusIcon,
  EyeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlayIcon,
  PauseIcon,
} from '@heroicons/react/24/outline';
import { checkApi, auditApi, resolveImageUrl } from '../services/api';
import { CheckItem, CheckHistory, ROIRegion } from '../types';
import { useReviewSettings } from '../stores/reviewSettingsStore';
import { useAuthStore } from '../stores/authStore';
import { useResizableWidth } from '../hooks/useResizableWidth';
import { formatDate } from '../utils/date';
import { logError } from '../utils/log';

// Image URL refresh interval (60 seconds - before 90s TTL expires)
const IMAGE_URL_REFRESH_INTERVAL = 60 * 1000;
import CheckImageViewer from '../components/check/CheckImageViewer';
import CheckContextPanel from '../components/check/CheckContextPanel';
import CheckHistoryPanel from '../components/check/CheckHistoryPanel';
import DecisionPanel from '../components/decision/DecisionPanel';
import NetworkIntelligencePanel from '../components/fraud/NetworkIntelligencePanel';
import FraudReportModal from '../components/fraud/FraudReportModal';
import EvidenceChainModal from '../components/decision/EvidenceChainModal';
import AssignModal from '../components/check/AssignModal';
import ItemViewsModal from '../components/check/ItemViewsModal';
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
  const navigate = useNavigate();
  const { autoAdvance, setAutoAdvance } = useReviewSettings();
  const [comparisonItem, setComparisonItem] = useState<CheckHistory | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [showFraudModal, setShowFraudModal] = useState(false);
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showViewsModal, setShowViewsModal] = useState(false);

  // User-resizable width for the Item Context column (the rest reacts to it).
  const {
    width: contextWidth,
    containerRef: layoutRef,
    onMouseDown: onContextResize,
  } = useResizableWidth({ storageKey: 'cr_item_context_width', defaultWidth: 340, min: 280, max: 640 });
  const canViewAudit = useAuthStore((s) => s.hasPermission('audit', 'view'));
  const canAssign = useAuthStore((s) => s.hasPermission('check_item', 'assign'));
  const canReportFraud = useAuthStore((s) => s.hasPermission('fraud', 'create'));

  const { data: item, isLoading, error, refetch } = useQuery<CheckItem>({
    queryKey: ['checkItem', itemId],
    queryFn: () => checkApi.getItem(itemId!),
    enabled: !!itemId,
    // Refetch periodically to get fresh signed image URLs before they expire
    // (signed URL TTL is 5 minutes; see IMAGE_SIGNED_URL_TTL_SECONDS)
    refetchInterval: IMAGE_URL_REFRESH_INTERVAL,
    // Only refetch when window is focused (save bandwidth when tab is hidden)
    refetchIntervalInBackground: false,
  });

  // Get adjacent items for navigation
  const { data: adjacentItems } = useQuery({
    queryKey: ['adjacentItems', itemId],
    queryFn: () => checkApi.getAdjacentItems(itemId!),
    enabled: !!itemId,
  });

  // Navigation handlers
  const goToPrevious = useCallback(() => {
    if (adjacentItems?.previous_id) {
      navigate(`/review/${adjacentItems.previous_id}`);
    }
  }, [adjacentItems?.previous_id, navigate]);

  const goToNext = useCallback(() => {
    if (adjacentItems?.next_id) {
      navigate(`/review/${adjacentItems.next_id}`);
    }
  }, [adjacentItems?.next_id, navigate]);

  // Handle decision completion - auto-advance to next item
  const handleDecisionMade = useCallback(() => {
    if (autoAdvance && adjacentItems?.next_id) {
      // Small delay to show success toast before navigating
      setTimeout(() => {
        navigate(`/review/${adjacentItems.next_id}`);
      }, 500);
    }
  }, [autoAdvance, adjacentItems?.next_id, navigate]);

  // Keyboard navigation (N for next, P for previous)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if typing in an input/textarea
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key.toLowerCase() === 'n' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        goToNext();
      } else if (e.key.toLowerCase() === 'p' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        goToPrevious();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goToNext, goToPrevious]);

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
      logError('Failed to generate packet:', error);
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
    const httpStatus = (error as { response?: { status?: number } } | null)?.response?.status;
    const message =
      httpStatus === 404
        ? 'This check item could not be found. It may have been processed or removed.'
        : 'Something went wrong while loading this check item.';
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{message}</p>
        {httpStatus !== 404 && (
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 px-4 py-2 text-sm font-medium rounded-md bg-primary-600 text-white hover:bg-primary-700"
          >
            Try Again
          </button>
        )}
        <Link to="/queue" className="text-primary-600 hover:underline mt-3 block">
          Return to Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-4">
          <Link
            to="/queue"
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeftIcon className="h-5 w-5 mr-1" />
            Back to Queue
          </Link>
          <div className="h-6 w-px bg-gray-300" />

          {/* Navigation Controls */}
          <div className="flex items-center space-x-2">
            <button
              onClick={goToPrevious}
              disabled={!adjacentItems?.previous_id}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              title="Previous item (P)"
            >
              <ChevronLeftIcon className="h-5 w-5" />
            </button>
            {adjacentItems && (
              <span className="text-sm text-gray-500 min-w-[80px] text-center">
                {adjacentItems.position} of {adjacentItems.total}
              </span>
            )}
            <button
              onClick={goToNext}
              disabled={!adjacentItems?.next_id}
              className="p-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              title="Next item (N)"
            >
              <ChevronRightIcon className="h-5 w-5" />
            </button>
          </div>

          <div className="h-6 w-px bg-gray-300" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Check Review: {item.account_number_masked}
            </h1>
            <div className="flex flex-wrap items-center gap-2 mt-1">
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
        <div className="flex flex-wrap items-center gap-2">
          {/* Auto-Advance Toggle */}
          <button
            onClick={() => setAutoAdvance(!autoAdvance)}
            className={`flex items-center px-3 py-2 rounded-lg border transition-colors ${
              autoAdvance
                ? 'bg-green-50 border-green-300 text-green-700'
                : 'bg-gray-50 border-gray-300 text-gray-600'
            }`}
            title={autoAdvance ? 'Auto-advance enabled' : 'Auto-advance disabled'}
          >
            {autoAdvance ? (
              <PlayIcon className="h-4 w-4 mr-1.5" />
            ) : (
              <PauseIcon className="h-4 w-4 mr-1.5" />
            )}
            <span className="text-sm font-medium">Auto-Advance</span>
          </button>

          {canReportFraud && (
            <button
              onClick={() => setShowFraudModal(true)}
              className="flex items-center px-3 py-2 text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100"
            >
              <ShieldExclamationIcon className="h-5 w-5 mr-1" />
              Report Fraud
            </button>
          )}
          {canAssign && (
            <button
              onClick={() => setShowAssignModal(true)}
              className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <UserPlusIcon className="h-5 w-5 mr-1" />
              Assign
            </button>
          )}
          {canViewAudit && (
            <button
              onClick={() => setShowViewsModal(true)}
              className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <EyeIcon className="h-5 w-5 mr-1" />
              Views
            </button>
          )}
          {canViewAudit && (
            <button
              onClick={() => setShowEvidenceModal(true)}
              className="flex items-center px-3 py-2 text-primary-700 bg-primary-50 border border-primary-200 rounded-lg hover:bg-primary-100"
            >
              <ShieldCheckIcon className="h-5 w-5 mr-1" />
              Verify Evidence
            </button>
          )}
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

      {/* Main Content.
          Left column: the Item Context card, running the full height of the
          working area (sticky so it stays in view while the right column
          scrolls). Right column: the check image(s) on top, then the
          supporting panels (history, network, decision) directly below them.
          Keeping the image in its own column stops the side-by-side
          comparison from overlapping the context/history cards. */}
      <div
        ref={layoutRef}
        className="grid grid-cols-1 gap-4 lg:[grid-template-columns:var(--ctx-w)_minmax(0,1fr)]"
        style={{ ['--ctx-w' as string]: `${contextWidth}px` }}
      >
        {/* Left: Item context, full height alongside the right column. The width
            is user-resizable via the drag handle on its right edge (lg+ only). */}
        <div className="relative lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-110px)] lg:overflow-y-auto">
          <CheckContextPanel item={item} />
          {/* Resize handle - sits on the column's right edge */}
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize item context"
            title="Drag to resize"
            onMouseDown={onContextResize}
            className="absolute top-0 -right-2 z-10 hidden h-full w-3 cursor-col-resize items-center justify-center lg:flex group"
          >
            <div className="h-12 w-1 rounded-full bg-gray-300 transition-colors group-hover:bg-primary-500" />
          </div>
        </div>

        {/* Right: check image(s) then the supporting panels */}
        <div className="min-w-0 space-y-4">
          {/* Check Image Viewer (side-by-side with historical when comparing) */}
          <div className="h-[48vh] min-h-[320px]">
            <div className={`grid gap-4 h-full ${showComparison ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1'}`}>
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
                      Historical Check - {formatDate(comparisonItem.check_date)}
                    </span>
                    <button
                      onClick={() => setShowComparison(false)}
                      className="text-gray-400 hover:text-white text-sm"
                    >
                      Close
                    </button>
                  </div>
                  <div className="flex-1 flex items-center justify-center overflow-hidden">
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

          {/* Decision / Review Recommendation panel - the primary action, kept
              directly under the image so it is always visible without needing a
              maximised window (previously it was the 3rd cell of a wrapping grid
              and fell below the fold on smaller screens). */}
          <DecisionPanel item={item} onDecisionMade={handleDecisionMade} />

          {/* Secondary context panels below the decision */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* History Panel */}
            <CheckHistoryPanel
              itemId={item.id}
              currentAmount={item.amount}
              onSelectComparison={(historyItem) => {
                setComparisonItem(historyItem);
                setShowComparison(true);
              }}
            />

            {/* Network Intelligence Panel */}
            <NetworkIntelligencePanel checkItemId={item.id} />
          </div>
        </div>
      </div>

      {/* Fraud Report Modal */}
      <FraudReportModal
        isOpen={showFraudModal}
        onClose={() => setShowFraudModal(false)}
        item={item}
      />

      {/* Evidence Chain Verification Modal */}
      {canViewAudit && (
        <EvidenceChainModal
          isOpen={showEvidenceModal}
          onClose={() => setShowEvidenceModal(false)}
          itemId={item.id}
        />
      )}

      {/* Assign Modal */}
      {canAssign && (
        <AssignModal
          isOpen={showAssignModal}
          onClose={() => setShowAssignModal(false)}
          item={item}
        />
      )}

      {/* Item Views Modal */}
      {canViewAudit && (
        <ItemViewsModal
          isOpen={showViewsModal}
          onClose={() => setShowViewsModal(false)}
          itemId={item.id}
        />
      )}
    </div>
  );
}
