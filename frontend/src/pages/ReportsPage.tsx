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

const COLORS = ['#22c55e', '#f97316', '#ef4444', '#6366f1', '#8b5cf6'];

export default function ReportsPage() {
  const [timeRange, setTimeRange] = useState(7);

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
