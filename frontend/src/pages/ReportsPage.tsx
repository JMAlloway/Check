import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { reportsApi } from '../services/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from 'recharts';
import {
  DocumentArrowDownIcon,
  DocumentTextIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';

const COLORS = ['#22c55e', '#f97316', '#ef4444', '#6366f1', '#8b5cf6'];

// PDF Report types
type ReportType = 'daily-activity' | 'daily-summary' | 'executive-overview';

export default function ReportsPage() {
  const [timeRange, setTimeRange] = useState(7);
  const [reportDateFrom, setReportDateFrom] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [reportDateTo, setReportDateTo] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [generatingReport, setGeneratingReport] = useState<ReportType | null>(null);

  // PDF export mutations
  const handleExportPdf = async (reportType: ReportType) => {
    setGeneratingReport(reportType);
    try {
      if (reportType === 'daily-activity') {
        await reportsApi.exportDailyActivityPdf(
          `${reportDateFrom}T00:00:00`,
          `${reportDateTo}T23:59:59`
        );
      } else if (reportType === 'daily-summary') {
        await reportsApi.exportDailySummaryPdf(
          `${reportDateFrom}T00:00:00`,
          `${reportDateTo}T23:59:59`
        );
      } else if (reportType === 'executive-overview') {
        await reportsApi.exportExecutiveOverviewPdf();
      }
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF report. Please try again.');
    } finally {
      setGeneratingReport(null);
    }
  };

  const { data: throughput } = useQuery({
    queryKey: ['throughput', timeRange],
    queryFn: () => reportsApi.getThroughput(timeRange),
  });

  const { data: decisions } = useQuery({
    queryKey: ['decisions', timeRange],
    queryFn: () => reportsApi.getDecisionReport(timeRange),
  });

  const { data: performance } = useQuery({
    queryKey: ['performance', timeRange],
    queryFn: () => reportsApi.getReviewerPerformance(timeRange),
  });

  const decisionPieData = decisions?.by_action
    ? Object.entries(decisions.by_action).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(Number(e.target.value))}
          className="rounded-lg border-gray-300 text-sm"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* PDF Report Generation */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Generate PDF Reports</h2>

        {/* Date Range Selector */}
        <div className="flex flex-wrap items-end gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
            <input
              type="date"
              value={reportDateFrom}
              onChange={(e) => setReportDateFrom(e.target.value)}
              className="rounded-lg border-gray-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
            <input
              type="date"
              value={reportDateTo}
              onChange={(e) => setReportDateTo(e.target.value)}
              className="rounded-lg border-gray-300 text-sm"
            />
          </div>
        </div>

        {/* Report Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Daily Activity Log */}
          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <ClipboardDocumentListIcon className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Daily Activity Log</h3>
                <p className="text-xs text-gray-500">Audit trail of all actions</p>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Detailed log of all decisions made, including reviewer, action, timestamps, and notes.
            </p>
            <button
              onClick={() => handleExportPdf('daily-activity')}
              disabled={generatingReport === 'daily-activity'}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <DocumentArrowDownIcon className="h-4 w-4" />
              {generatingReport === 'daily-activity' ? 'Generating...' : 'Download PDF'}
            </button>
          </div>

          {/* Daily Summary */}
          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <DocumentTextIcon className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Daily Summary</h3>
                <p className="text-xs text-gray-500">Overview of daily operations</p>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Summary statistics including items processed, approval rates, risk distribution, and reviewer activity.
            </p>
            <button
              onClick={() => handleExportPdf('daily-summary')}
              disabled={generatingReport === 'daily-summary'}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <DocumentArrowDownIcon className="h-4 w-4" />
              {generatingReport === 'daily-summary' ? 'Generating...' : 'Download PDF'}
            </button>
          </div>

          {/* Executive Overview */}
          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <ChartBarIcon className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Executive Overview</h3>
                <p className="text-xs text-gray-500">QoQ / MoM / YoY KPIs</p>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Executive summary with quarter-over-quarter, month-over-month, and year-over-year comparisons.
            </p>
            <button
              onClick={() => handleExportPdf('executive-overview')}
              disabled={generatingReport === 'executive-overview'}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <DocumentArrowDownIcon className="h-4 w-4" />
              {generatingReport === 'executive-overview' ? 'Generating...' : 'Download PDF'}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Throughput Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Daily Throughput</h2>
          <div className="h-64">
            {throughput?.daily ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={throughput.daily}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="received" stroke="#3b82f6" name="Received" />
                  <Line type="monotone" dataKey="processed" stroke="#22c55e" name="Processed" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Loading...
              </div>
            )}
          </div>
        </div>

        {/* Decision Breakdown */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Decision Breakdown</h2>
          <div className="h-64 flex items-center justify-center">
            {decisionPieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={decisionPieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {decisionPieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-gray-500">No decision data</div>
            )}
          </div>
          {decisions && (
            <div className="mt-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{decisions.approval_rate}%</p>
              <p className="text-sm text-gray-500">Approval Rate</p>
            </div>
          )}
        </div>

        {/* Reviewer Performance */}
        <div className="bg-white rounded-lg shadow p-6 lg:col-span-2">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Reviewer Performance</h2>
          <div className="h-64">
            {performance?.reviewers ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={performance.reviewers.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="username" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="total_decisions" fill="#3b82f6" name="Total Decisions" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Loading...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      {decisions && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-3xl font-bold text-gray-900">{decisions.total_decisions}</p>
              <p className="text-sm text-gray-500">Total Decisions</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-3xl font-bold text-green-600">{decisions.by_action?.approve || 0}</p>
              <p className="text-sm text-gray-500">Approved</p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <p className="text-3xl font-bold text-orange-600">{decisions.by_action?.return || 0}</p>
              <p className="text-sm text-gray-500">Returned</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-3xl font-bold text-red-600">{decisions.by_action?.reject || 0}</p>
              <p className="text-sm text-gray-500">Rejected</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
