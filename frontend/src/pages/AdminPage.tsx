import { useState } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  UsersIcon,
  QueueListIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const adminNav = [
  { name: 'Users', href: '/admin/users', icon: UsersIcon },
  { name: 'Queues', href: '/admin/queues', icon: QueueListIcon },
  { name: 'Policies', href: '/admin/policies', icon: DocumentTextIcon },
  { name: 'Audit Log', href: '/admin/audit', icon: ClipboardDocumentListIcon },
];

function UsersAdmin() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">User Management</h2>
      <p className="text-gray-500">
        User management interface coming soon. You will be able to:
      </p>
      <ul className="list-disc list-inside mt-4 text-gray-600 space-y-2">
        <li>Create and manage user accounts</li>
        <li>Assign roles and permissions</li>
        <li>Set up multi-factor authentication</li>
        <li>Configure IP restrictions</li>
        <li>View user activity logs</li>
      </ul>
    </div>
  );
}

function QueuesAdmin() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Queue Management</h2>
      <p className="text-gray-500">
        Queue management interface coming soon. You will be able to:
      </p>
      <ul className="list-disc list-inside mt-4 text-gray-600 space-y-2">
        <li>Create and configure review queues</li>
        <li>Set SLA thresholds and alerts</li>
        <li>Define routing rules</li>
        <li>Assign users to queues</li>
        <li>Monitor queue performance</li>
      </ul>
    </div>
  );
}

function PoliciesAdmin() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Policy Management</h2>
      <p className="text-gray-500">
        Policy management interface coming soon. You will be able to:
      </p>
      <ul className="list-disc list-inside mt-4 text-gray-600 space-y-2">
        <li>Create and version policy rules</li>
        <li>Define dual control thresholds</li>
        <li>Configure escalation logic</li>
        <li>Set up required reason codes</li>
        <li>View policy audit history</li>
      </ul>
    </div>
  );
}

function AuditLogAdmin() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Audit Log</h2>
      <p className="text-gray-500">
        Audit log interface coming soon. You will be able to:
      </p>
      <ul className="list-disc list-inside mt-4 text-gray-600 space-y-2">
        <li>Search and filter audit logs</li>
        <li>View user activity history</li>
        <li>Export audit reports</li>
        <li>Track configuration changes</li>
        <li>Monitor security events</li>
      </ul>
    </div>
  );
}

export default function AdminPage() {
  const location = useLocation();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Administration</h1>

      <div className="flex gap-6">
        {/* Sidebar Navigation */}
        <div className="w-64 flex-shrink-0">
          <nav className="bg-white rounded-lg shadow p-4">
            <ul className="space-y-1">
              {adminNav.map((item) => (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={clsx(
                      'flex items-center px-3 py-2 text-sm font-medium rounded-lg',
                      location.pathname === item.href
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-700 hover:bg-gray-50'
                    )}
                  >
                    <item.icon className="h-5 w-5 mr-3" />
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        {/* Content Area */}
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<UsersAdmin />} />
            <Route path="/users" element={<UsersAdmin />} />
            <Route path="/queues" element={<QueuesAdmin />} />
            <Route path="/policies" element={<PoliciesAdmin />} />
            <Route path="/audit" element={<AuditLogAdmin />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
