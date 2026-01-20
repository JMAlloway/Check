import { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  UsersIcon,
  QueueListIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  PlusIcon,
  PencilIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
  FunnelIcon,
  ArrowPathIcon,
  ServerIcon,
  KeyIcon,
  SignalIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
  ChartBarSquareIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { userApi, queueAdminApi, policyApi, auditLogApi, imageConnectorApi, systemApi, reportsApi } from '../services/api';
import { format } from 'date-fns';

const adminNav = [
  { name: 'System Metrics', href: '/admin/metrics', icon: ChartBarSquareIcon },
  { name: 'Users', href: '/admin/users', icon: UsersIcon },
  { name: 'Queues', href: '/admin/queues', icon: QueueListIcon },
  { name: 'Policies', href: '/admin/policies', icon: DocumentTextIcon },
  { name: 'Image Connectors', href: '/admin/connectors', icon: ServerIcon },
  { name: 'Audit Log', href: '/admin/audit', icon: ClipboardDocumentListIcon },
];

// ============================================================================
// User Management Component
// ============================================================================

interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  is_active: boolean;
  department?: string;
  roles: string[];
  last_login?: string;
}

interface Role {
  id: string;
  name: string;
  description?: string;
  is_system: boolean;
  permissions: Permission[];
}

interface Permission {
  id: string;
  name: string;
  description?: string;
  resource: string;
  action: string;
}

function UsersAdmin() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [page, setPage] = useState(1);

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users', page, search, showInactive],
    queryFn: () => userApi.getUsers({
      page,
      page_size: 20,
      search: search || undefined,
      is_active: showInactive ? undefined : true,
    }),
  });

  const { data: roles } = useQuery({
    queryKey: ['roles'],
    queryFn: () => userApi.getRoles(),
  });

  const createUserMutation = useMutation({
    mutationFn: userApi.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowCreateModal(false);
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: Parameters<typeof userApi.updateUser>[1] }) =>
      userApi.updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setEditingUser(null);
    },
  });

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Add User
            </button>
          </div>

          {/* Filters */}
          <div className="mt-4 flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search users..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              Show inactive
            </label>
          </div>
        </div>

        {/* Users Table */}
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading users...</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Department</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Roles</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Login</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {usersData?.items?.map((user: User) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                          <span className="text-primary-700 font-medium">
                            {user.full_name?.charAt(0) || user.username.charAt(0)}
                          </span>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">{user.full_name}</div>
                          <div className="text-sm text-gray-500">{user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{user.username}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{user.department || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {user.roles?.map((role) => (
                          <span
                            key={role}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.is_active ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          <CheckCircleIcon className="h-3 w-3 mr-1" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          <XCircleIcon className="h-3 w-3 mr-1" />
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {user.last_login ? format(new Date(user.last_login), 'MMM d, yyyy HH:mm') : 'Never'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => setEditingUser(user)}
                        className="text-primary-600 hover:text-primary-900"
                      >
                        <PencilIcon className="h-5 w-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {usersData && usersData.total_pages > 1 && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-700">
              Page {page} of {usersData.total_pages} ({usersData.total} total)
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={!usersData.has_previous}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!usersData.has_next}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <UserFormModal
          roles={roles || []}
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createUserMutation.mutate(data)}
          isLoading={createUserMutation.isPending}
        />
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <UserFormModal
          user={editingUser}
          roles={roles || []}
          onClose={() => setEditingUser(null)}
          onSubmit={(data) => updateUserMutation.mutate({ userId: editingUser.id, data })}
          isLoading={updateUserMutation.isPending}
        />
      )}
    </div>
  );
}

function UserFormModal({
  user,
  roles,
  onClose,
  onSubmit,
  isLoading,
}: {
  user?: User;
  roles: Role[];
  onClose: () => void;
  onSubmit: (data: any) => void;
  isLoading: boolean;
}) {
  const [formData, setFormData] = useState({
    email: user?.email || '',
    username: user?.username || '',
    full_name: user?.full_name || '',
    password: '',
    department: user?.department || '',
    is_active: user?.is_active ?? true,
    role_ids: [] as string[],
  });

  useEffect(() => {
    if (user && roles.length > 0) {
      const userRoleIds = roles
        .filter((r) => user.roles?.includes(r.name))
        .map((r) => r.id);
      setFormData((prev) => ({ ...prev, role_ids: userRoleIds }));
    }
  }, [user, roles]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const submitData = user
      ? {
          email: formData.email,
          full_name: formData.full_name,
          department: formData.department || undefined,
          is_active: formData.is_active,
          role_ids: formData.role_ids,
        }
      : {
          ...formData,
          department: formData.department || undefined,
        };
    onSubmit(submitData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            {user ? 'Edit User' : 'Create User'}
          </h3>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {!user && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                type="text"
                required
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              required
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {!user && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
            <input
              type="text"
              value={formData.department}
              onChange={(e) => setFormData({ ...formData, department: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Roles</label>
            <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3">
              {roles.map((role) => (
                <label key={role.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.role_ids.includes(role.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setFormData({ ...formData, role_ids: [...formData.role_ids, role.id] });
                      } else {
                        setFormData({ ...formData, role_ids: formData.role_ids.filter((id) => id !== role.id) });
                      }
                    }}
                    className="rounded border-gray-300 text-primary-600"
                  />
                  <span className="text-sm text-gray-700">{role.name}</span>
                  {role.is_system && (
                    <span className="text-xs text-gray-500">(system)</span>
                  )}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded border-gray-300 text-primary-600"
              />
              <span className="text-sm font-medium text-gray-700">Active</span>
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : user ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// Queue Management Component
// ============================================================================

interface Queue {
  id: string;
  name: string;
  description?: string;
  queue_type: string;
  sla_hours?: number;
  warning_threshold_minutes?: number;
  is_active: boolean;
  display_order: number;
  current_item_count: number;
  items_processed_today: number;
}

function QueuesAdmin() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingQueue, setEditingQueue] = useState<Queue | null>(null);
  const [selectedQueue, setSelectedQueue] = useState<string | null>(null);

  const { data: queues, isLoading } = useQuery({
    queryKey: ['admin-queues'],
    queryFn: () => queueAdminApi.getQueues(true),
  });

  const createQueueMutation = useMutation({
    mutationFn: queueAdminApi.createQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-queues'] });
      setShowCreateModal(false);
    },
  });

  const updateQueueMutation = useMutation({
    mutationFn: ({ queueId, data }: { queueId: string; data: Parameters<typeof queueAdminApi.updateQueue>[1] }) =>
      queueAdminApi.updateQueue(queueId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-queues'] });
      setEditingQueue(null);
    },
  });

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Queue Management</h2>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Add Queue
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading queues...</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {queues?.map((queue: Queue) => (
              <div key={queue.id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-gray-900">{queue.name}</h3>
                      <span
                        className={clsx(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          queue.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-600'
                        )}
                      >
                        {queue.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">
                        {queue.queue_type}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-500">{queue.description || 'No description'}</p>

                    <div className="mt-3 flex items-center gap-6 text-sm">
                      <div>
                        <span className="text-gray-500">Items in queue:</span>{' '}
                        <span className="font-medium text-gray-900">{queue.current_item_count}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Processed today:</span>{' '}
                        <span className="font-medium text-gray-900">{queue.items_processed_today}</span>
                      </div>
                      {queue.sla_hours && (
                        <div>
                          <span className="text-gray-500">SLA:</span>{' '}
                          <span className="font-medium text-gray-900">{queue.sla_hours}h</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedQueue(selectedQueue === queue.id ? null : queue.id)}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      {selectedQueue === queue.id ? 'Hide' : 'Assignments'}
                    </button>
                    <button
                      onClick={() => setEditingQueue(queue)}
                      className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
                    >
                      <PencilIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>

                {selectedQueue === queue.id && (
                  <QueueAssignments queueId={queue.id} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Queue Modal */}
      {showCreateModal && (
        <QueueFormModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createQueueMutation.mutate(data)}
          isLoading={createQueueMutation.isPending}
        />
      )}

      {/* Edit Queue Modal */}
      {editingQueue && (
        <QueueFormModal
          queue={editingQueue}
          onClose={() => setEditingQueue(null)}
          onSubmit={(data) => updateQueueMutation.mutate({ queueId: editingQueue.id, data })}
          isLoading={updateQueueMutation.isPending}
        />
      )}
    </div>
  );
}

function QueueAssignments({ queueId }: { queueId: string }) {
  const { data: assignments, isLoading } = useQuery({
    queryKey: ['queue-assignments', queueId],
    queryFn: () => queueAdminApi.getAssignments(queueId),
  });

  if (isLoading) {
    return <div className="mt-4 p-4 text-sm text-gray-500">Loading assignments...</div>;
  }

  if (!assignments || assignments.length === 0) {
    return (
      <div className="mt-4 p-4 bg-gray-50 rounded-lg text-sm text-gray-500">
        No users assigned to this queue.
      </div>
    );
  }

  return (
    <div className="mt-4 bg-gray-50 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-900 mb-3">Assigned Users</h4>
      <div className="space-y-2">
        {assignments.map((assignment: any) => (
          <div key={assignment.id} className="flex items-center justify-between bg-white rounded p-3">
            <div>
              <span className="font-medium text-gray-900">{assignment.user_name || 'User'}</span>
              <div className="flex gap-2 mt-1">
                {assignment.can_review && (
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">Can Review</span>
                )}
                {assignment.can_approve && (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">Can Approve</span>
                )}
              </div>
            </div>
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded',
              assignment.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
            )}>
              {assignment.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function QueueFormModal({
  queue,
  onClose,
  onSubmit,
  isLoading,
}: {
  queue?: Queue;
  onClose: () => void;
  onSubmit: (data: any) => void;
  isLoading: boolean;
}) {
  const [formData, setFormData] = useState({
    name: queue?.name || '',
    description: queue?.description || '',
    queue_type: queue?.queue_type || 'general',
    sla_hours: queue?.sla_hours || 24,
    warning_threshold_minutes: queue?.warning_threshold_minutes || 120,
    is_active: queue?.is_active ?? true,
    display_order: queue?.display_order || 0,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            {queue ? 'Edit Queue' : 'Create Queue'}
          </h3>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={formData.queue_type}
                onChange={(e) => setFormData({ ...formData, queue_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              >
                <option value="general">General</option>
                <option value="high_value">High Value</option>
                <option value="escalation">Escalation</option>
                <option value="fraud">Fraud</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">SLA (hours)</label>
              <input
                type="number"
                value={formData.sla_hours}
                onChange={(e) => setFormData({ ...formData, sla_hours: parseInt(e.target.value) || 24 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded border-gray-300 text-primary-600"
              />
              <span className="text-sm font-medium text-gray-700">Active</span>
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : queue ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// Policy Management Component
// ============================================================================

interface Policy {
  id: string;
  name: string;
  description?: string;
  status: string;
  is_default: boolean;
  current_version_number?: number;
  rules_count?: number;
}

function PoliciesAdmin() {
  const [selectedPolicy, setSelectedPolicy] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: policies, isLoading } = useQuery({
    queryKey: ['policies'],
    queryFn: () => policyApi.getPolicies(),
  });

  const { data: policyDetail } = useQuery({
    queryKey: ['policy', selectedPolicy],
    queryFn: () => policyApi.getPolicy(selectedPolicy!),
    enabled: !!selectedPolicy,
  });

  const queryClient = useQueryClient();
  const activateMutation = useMutation({
    mutationFn: (policyId: string) => policyApi.activatePolicy(policyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policies'] });
    },
  });

  const createPolicyMutation = useMutation({
    mutationFn: policyApi.createPolicy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policies'] });
      setShowCreateModal(false);
    },
    onError: (error: any) => {
      console.error('Failed to create policy:', error);
      alert(`Failed to create policy: ${error.response?.data?.detail || error.message}`);
    },
  });

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Policy Management</h2>
              <p className="text-sm text-gray-500 mt-1">
                Policies define routing, escalation, and approval rules
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Create Policy
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading policies...</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {policies?.map((policy: Policy) => (
              <div key={policy.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-gray-900">{policy.name}</h3>
                      <span
                        className={clsx(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          policy.status === 'active' && 'bg-green-100 text-green-800',
                          policy.status === 'draft' && 'bg-yellow-100 text-yellow-800',
                          policy.status === 'archived' && 'bg-gray-100 text-gray-600'
                        )}
                      >
                        {policy.status}
                      </span>
                      {policy.is_default && (
                        <span className="px-2 py-0.5 rounded bg-purple-100 text-purple-700 text-xs font-medium">
                          Default
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-gray-500">{policy.description || 'No description'}</p>

                    <div className="mt-3 flex items-center gap-6 text-sm text-gray-500">
                      <span>Version: {policy.current_version_number || 'None'}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedPolicy(selectedPolicy === policy.id ? null : policy.id)}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      {selectedPolicy === policy.id ? 'Hide Details' : 'View Details'}
                    </button>
                    {policy.status === 'draft' && (
                      <button
                        onClick={() => activateMutation.mutate(policy.id)}
                        disabled={activateMutation.isPending}
                        className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                      >
                        Activate
                      </button>
                    )}
                  </div>
                </div>

                {selectedPolicy === policy.id && policyDetail && (
                  <PolicyDetails policy={policyDetail} />
                )}
              </div>
            ))}

            {(!policies || policies.length === 0) && (
              <div className="p-8 text-center text-gray-500">
                No policies configured yet. Click "Create Policy" to add one.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Policy Modal */}
      {showCreateModal && (
        <PolicyFormModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createPolicyMutation.mutate(data)}
          isLoading={createPolicyMutation.isPending}
        />
      )}
    </div>
  );
}

function PolicyFormModal({
  onClose,
  onSubmit,
  isLoading,
}: {
  onClose: () => void;
  onSubmit: (data: any) => void;
  isLoading: boolean;
}) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    applies_to_account_types: [] as string[],
    applies_to_branches: [] as string[],
  });

  const [rules, setRules] = useState<Array<{
    name: string;
    description: string;
    rule_type: string;
    priority: number;
    is_enabled: boolean;
    amount_threshold?: number;
    risk_level_threshold?: string;
  }>>([]);

  const [showAddRule, setShowAddRule] = useState(false);
  const [newRule, setNewRule] = useState({
    name: '',
    description: '',
    rule_type: 'routing',
    priority: 1,
    is_enabled: true,
    amount_threshold: undefined as number | undefined,
    risk_level_threshold: '',
  });

  const handleAddRule = () => {
    setRules([...rules, { ...newRule }]);
    setNewRule({
      name: '',
      description: '',
      rule_type: 'routing',
      priority: rules.length + 2,
      is_enabled: true,
      amount_threshold: undefined,
      risk_level_threshold: '',
    });
    setShowAddRule(false);
  };

  const handleRemoveRule = (index: number) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const policyData: any = {
      name: formData.name,
      description: formData.description || undefined,
      applies_to_account_types: formData.applies_to_account_types.length > 0 ? formData.applies_to_account_types : undefined,
      applies_to_branches: formData.applies_to_branches.length > 0 ? formData.applies_to_branches : undefined,
    };

    if (rules.length > 0) {
      policyData.initial_version = {
        effective_date: new Date().toISOString().split('T')[0],
        change_notes: 'Initial version',
        rules: rules.map((rule) => ({
          ...rule,
          conditions: [],
          actions: [{ type: 'route_to_queue', params: {} }],
          amount_threshold: rule.amount_threshold || undefined,
          risk_level_threshold: rule.risk_level_threshold || undefined,
        })),
      };
    }

    onSubmit(policyData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Create Policy</h3>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Policy Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., High Value Check Policy"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                placeholder="Describe what this policy does..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          {/* Rules Section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-sm font-medium text-gray-700">Policy Rules</label>
              <button
                type="button"
                onClick={() => setShowAddRule(true)}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                + Add Rule
              </button>
            </div>

            {rules.length === 0 ? (
              <div className="text-sm text-gray-500 bg-gray-50 rounded-lg p-4 text-center">
                No rules added yet. Add rules to define how checks are routed and processed.
              </div>
            ) : (
              <div className="space-y-2">
                {rules.map((rule, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                    <div>
                      <span className="font-medium text-gray-900">{rule.name}</span>
                      <div className="flex gap-2 mt-1">
                        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">{rule.rule_type}</span>
                        <span className="text-xs text-gray-500">Priority: {rule.priority}</span>
                        {rule.amount_threshold && (
                          <span className="text-xs text-gray-500">${rule.amount_threshold.toLocaleString()}+</span>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      className="text-red-600 hover:text-red-700 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add Rule Form */}
            {showAddRule && (
              <div className="mt-4 p-4 border border-gray-200 rounded-lg bg-gray-50">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Add Rule</h4>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Rule Name</label>
                      <input
                        type="text"
                        value={newRule.name}
                        onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                        placeholder="e.g., Route High Value"
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Type</label>
                      <select
                        value={newRule.rule_type}
                        onChange={(e) => setNewRule({ ...newRule, rule_type: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                      >
                        <option value="routing">Routing</option>
                        <option value="escalation">Escalation</option>
                        <option value="dual_control">Dual Control</option>
                        <option value="auto_approve">Auto Approve</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Priority</label>
                      <input
                        type="number"
                        value={newRule.priority}
                        onChange={(e) => setNewRule({ ...newRule, priority: parseInt(e.target.value) || 1 })}
                        min={1}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Amount Threshold ($)</label>
                      <input
                        type="number"
                        value={newRule.amount_threshold || ''}
                        onChange={(e) => setNewRule({ ...newRule, amount_threshold: e.target.value ? parseInt(e.target.value) : undefined })}
                        placeholder="e.g., 10000"
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Risk Level Threshold</label>
                    <select
                      value={newRule.risk_level_threshold}
                      onChange={(e) => setNewRule({ ...newRule, risk_level_threshold: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                    >
                      <option value="">Any risk level</option>
                      <option value="low">Low and above</option>
                      <option value="medium">Medium and above</option>
                      <option value="high">High and above</option>
                      <option value="critical">Critical only</option>
                    </select>
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowAddRule(false)}
                      className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleAddRule}
                      disabled={!newRule.name}
                      className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                    >
                      Add Rule
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !formData.name}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? 'Creating...' : 'Create Policy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PolicyDetails({ policy }: { policy: any }) {
  const currentVersion = policy.current_version;

  return (
    <div className="mt-4 bg-gray-50 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-900 mb-3">
        Current Version Details (v{currentVersion?.version_number || 'N/A'})
      </h4>

      {currentVersion?.rules && currentVersion.rules.length > 0 ? (
        <div className="space-y-3">
          {currentVersion.rules.map((rule: any, idx: number) => (
            <div key={rule.id || idx} className="bg-white rounded p-3 border border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">{rule.name}</span>
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                    {rule.rule_type}
                  </span>
                  <span className="text-xs text-gray-500">Priority: {rule.priority}</span>
                </div>
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded',
                  rule.is_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                )}>
                  {rule.is_enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              {rule.description && (
                <p className="mt-1 text-sm text-gray-500">{rule.description}</p>
              )}
              {rule.amount_threshold && (
                <p className="mt-1 text-xs text-gray-500">
                  Amount threshold: ${rule.amount_threshold.toLocaleString()}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500">No rules defined for this version.</p>
      )}

      {currentVersion?.change_notes && (
        <div className="mt-4 p-3 bg-blue-50 rounded text-sm text-blue-700">
          <strong>Change notes:</strong> {currentVersion.change_notes}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Audit Log Component
// ============================================================================

interface AuditLog {
  id: string;
  timestamp: string;
  user_id?: string;
  username?: string;
  ip_address?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  description?: string;
  before_value?: Record<string, unknown>;
  after_value?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

function AuditLogAdmin() {
  const [filters, setFilters] = useState({
    action: '',
    resource_type: '',
    user_id: '',
    date_from: '',
    date_to: '',
  });
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  const { data: logsData, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', page, filters],
    queryFn: () => auditLogApi.searchLogs({
      page,
      page_size: 50,
      action: filters.action || undefined,
      resource_type: filters.resource_type || undefined,
      user_id: filters.user_id || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    }),
  });

  const actionTypes = [
    'check_viewed', 'check_assigned', 'decision_created', 'decision_approved',
    'user_created', 'user_updated', 'queue_created', 'queue_updated',
    'policy_created', 'policy_activated', 'audit_packet_generated',
  ];

  const resourceTypes = ['check_item', 'decision', 'user', 'queue', 'policy', 'role'];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Audit Log</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetch()}
                className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
              >
                <ArrowPathIcon className="h-5 w-5" />
              </button>
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={clsx(
                  'inline-flex items-center px-3 py-2 border rounded-lg text-sm',
                  showFilters ? 'border-primary-500 text-primary-600 bg-primary-50' : 'border-gray-300 text-gray-700'
                )}
              >
                <FunnelIcon className="h-4 w-4 mr-2" />
                Filters
              </button>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Action</label>
                  <select
                    value={filters.action}
                    onChange={(e) => setFilters({ ...filters, action: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  >
                    <option value="">All actions</option>
                    {actionTypes.map((action) => (
                      <option key={action} value={action}>{action.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Resource Type</label>
                  <select
                    value={filters.resource_type}
                    onChange={(e) => setFilters({ ...filters, resource_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  >
                    <option value="">All types</option>
                    {resourceTypes.map((type) => (
                      <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">From Date</label>
                  <input
                    type="date"
                    value={filters.date_from}
                    onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">To Date</label>
                  <input
                    type="date"
                    value={filters.date_to}
                    onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    onClick={() => setFilters({ action: '', resource_type: '', user_id: '', date_from: '', date_to: '' })}
                    className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
                  >
                    Clear filters
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Audit Log Table */}
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading audit logs...</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resource</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP Address</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logsData?.items?.map((log: AuditLog) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {format(new Date(log.timestamp), 'MMM d, yyyy HH:mm:ss')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm font-medium text-gray-900">{log.username || 'System'}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        {log.action?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className="text-gray-500">{log.resource_type}</span>
                      {log.resource_id && (
                        <span className="ml-1 text-gray-400">#{log.resource_id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-md truncate">
                      {log.description || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                      {log.ip_address || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {logsData && logsData.total_pages > 1 && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-700">
              Page {page} of {logsData.total_pages} ({logsData.total} total entries)
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={!logsData.has_previous}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!logsData.has_next}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Image Connectors Management Component
// ============================================================================

interface ImageConnector {
  id: string;
  connector_id: string;
  name: string;
  description?: string;
  base_url: string;
  status: string;
  is_enabled: boolean;
  public_key_id: string;
  public_key_expires_at?: string;
  secondary_public_key_id?: string;
  token_expiry_seconds: number;
  last_health_check_at?: string;
  last_health_check_status?: string;
  last_health_check_latency_ms?: number;
  health_check_failure_count: number;
  last_successful_request_at?: string;
  created_at: string;
  updated_at: string;
}

function ImageConnectorsAdmin() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingConnector, setEditingConnector] = useState<ImageConnector | null>(null);
  const [showKeyModal, setShowKeyModal] = useState<ImageConnector | null>(null);
  const [testingConnector, setTestingConnector] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ connectorId: string; success: boolean; latency?: number; error?: string } | null>(null);

  const { data: connectors, isLoading, refetch } = useQuery({
    queryKey: ['image-connectors'],
    queryFn: () => imageConnectorApi.getConnectors(),
  });

  const createMutation = useMutation({
    mutationFn: imageConnectorApi.createConnector,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-connectors'] });
      setShowCreateModal(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ connectorId, data }: { connectorId: string; data: Parameters<typeof imageConnectorApi.updateConnector>[1] }) =>
      imageConnectorApi.updateConnector(connectorId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-connectors'] });
      setEditingConnector(null);
    },
  });

  const enableMutation = useMutation({
    mutationFn: imageConnectorApi.enableConnector,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['image-connectors'] }),
  });

  const disableMutation = useMutation({
    mutationFn: imageConnectorApi.disableConnector,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['image-connectors'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: imageConnectorApi.deleteConnector,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['image-connectors'] }),
  });

  const testMutation = useMutation({
    mutationFn: imageConnectorApi.testConnector,
    onSuccess: (data, connectorId) => {
      setTestResult({ connectorId, success: data.success, latency: data.latency_ms, error: data.error });
      queryClient.invalidateQueries({ queryKey: ['image-connectors'] });
    },
    onError: (error: any, connectorId) => {
      setTestResult({ connectorId, success: false, error: error.message || 'Connection failed' });
    },
    onSettled: () => setTestingConnector(null),
  });

  const handleTest = (connectorId: string) => {
    setTestingConnector(connectorId);
    setTestResult(null);
    testMutation.mutate(connectorId);
  };

  const handleDelete = (connector: ImageConnector) => {
    if (confirm(`Are you sure you want to delete connector "${connector.name}"? This action cannot be undone.`)) {
      deleteMutation.mutate(connector.connector_id);
    }
  };

  const getStatusBadge = (connector: ImageConnector) => {
    if (!connector.is_enabled) {
      return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Disabled</span>;
    }
    switch (connector.status) {
      case 'healthy':
        return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Healthy</span>;
      case 'degraded':
        return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Degraded</span>;
      case 'unhealthy':
        return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Unhealthy</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">{connector.status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Image Connectors</h2>
              <p className="text-sm text-gray-500 mt-1">
                Manage bank-side connectors for secure check image retrieval
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetch()}
                className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
              >
                <ArrowPathIcon className="h-5 w-5" />
              </button>
              <button
                onClick={() => setShowCreateModal(true)}
                className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                <PlusIcon className="h-5 w-5 mr-2" />
                Add Connector
              </button>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading connectors...</div>
        ) : !connectors || connectors.length === 0 ? (
          <div className="p-8 text-center">
            <ServerIcon className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Connectors Configured</h3>
            <p className="text-gray-500 mb-4">
              Add a bank-side connector to enable secure check image retrieval.
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Add Connector
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {connectors.map((connector: ImageConnector) => (
              <div key={connector.id} className="p-6 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-medium text-gray-900">{connector.name}</h3>
                      {getStatusBadge(connector)}
                      {connector.health_check_failure_count > 0 && (
                        <span className="inline-flex items-center text-xs text-amber-600">
                          <ExclamationTriangleIcon className="h-4 w-4 mr-1" />
                          {connector.health_check_failure_count} failures
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-gray-500">{connector.description || 'No description'}</p>

                    <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Connector ID:</span>{' '}
                        <span className="font-mono text-gray-900">{connector.connector_id}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Base URL:</span>{' '}
                        <span className="font-mono text-gray-900 text-xs">{connector.base_url}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Token TTL:</span>{' '}
                        <span className="text-gray-900">{connector.token_expiry_seconds}s</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Key ID:</span>{' '}
                        <span className="font-mono text-gray-900 text-xs">{connector.public_key_id.slice(0, 12)}...</span>
                      </div>
                    </div>

                    {connector.last_health_check_at && (
                      <div className="mt-2 text-xs text-gray-500">
                        Last health check: {format(new Date(connector.last_health_check_at), 'MMM d, yyyy HH:mm:ss')}
                        {connector.last_health_check_latency_ms && (
                          <span className="ml-2">({connector.last_health_check_latency_ms}ms)</span>
                        )}
                      </div>
                    )}

                    {/* Test Result */}
                    {testResult && testResult.connectorId === connector.connector_id && (
                      <div className={clsx(
                        'mt-3 p-3 rounded-lg text-sm',
                        testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                      )}>
                        {testResult.success ? (
                          <span className="flex items-center">
                            <CheckCircleIcon className="h-4 w-4 mr-2" />
                            Connection successful{testResult.latency && ` (${testResult.latency}ms)`}
                          </span>
                        ) : (
                          <span className="flex items-center">
                            <XCircleIcon className="h-4 w-4 mr-2" />
                            Connection failed: {testResult.error}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => handleTest(connector.connector_id)}
                      disabled={testingConnector === connector.connector_id}
                      className="inline-flex items-center px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                    >
                      <SignalIcon className={clsx('h-4 w-4 mr-1', testingConnector === connector.connector_id && 'animate-pulse')} />
                      {testingConnector === connector.connector_id ? 'Testing...' : 'Test'}
                    </button>

                    {connector.is_enabled ? (
                      <button
                        onClick={() => disableMutation.mutate(connector.connector_id)}
                        disabled={disableMutation.isPending}
                        className="px-3 py-1.5 text-sm border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50"
                      >
                        Disable
                      </button>
                    ) : (
                      <button
                        onClick={() => enableMutation.mutate(connector.connector_id)}
                        disabled={enableMutation.isPending}
                        className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Enable
                      </button>
                    )}

                    <button
                      onClick={() => setShowKeyModal(connector)}
                      className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
                      title="Key Management"
                    >
                      <KeyIcon className="h-5 w-5" />
                    </button>

                    <button
                      onClick={() => setEditingConnector(connector)}
                      className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
                      title="Edit"
                    >
                      <PencilIcon className="h-5 w-5" />
                    </button>

                    <button
                      onClick={() => handleDelete(connector)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg"
                      title="Delete"
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Connector Modal */}
      {showCreateModal && (
        <ConnectorFormModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isLoading={createMutation.isPending}
          error={createMutation.error}
        />
      )}

      {/* Edit Connector Modal */}
      {editingConnector && (
        <ConnectorFormModal
          connector={editingConnector}
          onClose={() => setEditingConnector(null)}
          onSubmit={(data) => updateMutation.mutate({ connectorId: editingConnector.connector_id, data })}
          isLoading={updateMutation.isPending}
          error={updateMutation.error}
        />
      )}

      {/* Key Management Modal */}
      {showKeyModal && (
        <KeyManagementModal
          connector={showKeyModal}
          onClose={() => setShowKeyModal(null)}
        />
      )}
    </div>
  );
}

function ConnectorFormModal({
  connector,
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  connector?: ImageConnector;
  onClose: () => void;
  onSubmit: (data: any) => void;
  isLoading: boolean;
  error?: Error | null;
}) {
  const [formData, setFormData] = useState({
    connector_id: connector?.connector_id || '',
    name: connector?.name || '',
    description: connector?.description || '',
    base_url: connector?.base_url || '',
    public_key_pem: '',
    token_expiry_seconds: connector?.token_expiry_seconds || 120,
  });
  const [generatedKeys, setGeneratedKeys] = useState<{ private_key_pem: string; public_key_pem: string } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateKeys = async () => {
    setIsGenerating(true);
    try {
      const keys = await imageConnectorApi.generateKeypair();
      setGeneratedKeys(keys);
      setFormData({ ...formData, public_key_pem: keys.public_key_pem });
    } catch (err) {
      console.error('Failed to generate keys:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (connector) {
      // Update - only send changed fields
      const updateData: any = {};
      if (formData.name !== connector.name) updateData.name = formData.name;
      if (formData.description !== connector.description) updateData.description = formData.description;
      if (formData.base_url !== connector.base_url) updateData.base_url = formData.base_url;
      if (formData.token_expiry_seconds !== connector.token_expiry_seconds) updateData.token_expiry_seconds = formData.token_expiry_seconds;
      onSubmit(updateData);
    } else {
      // Create
      onSubmit(formData);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            {connector ? 'Edit Connector' : 'Add Image Connector'}
          </h3>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {(error as any)?.response?.data?.detail || error.message}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Connector ID</label>
              <input
                type="text"
                required
                disabled={!!connector}
                value={formData.connector_id}
                onChange={(e) => setFormData({ ...formData, connector_id: e.target.value })}
                placeholder="connector-prod-001"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100"
              />
              <p className="mt-1 text-xs text-gray-500">Must match connector config</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Primary DC Connector"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Production connector in primary data center"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
            <input
              type="url"
              required
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              placeholder="https://connector.bank.local:8443"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Token Expiry (seconds)</label>
            <input
              type="number"
              required
              min={60}
              max={300}
              value={formData.token_expiry_seconds}
              onChange={(e) => setFormData({ ...formData, token_expiry_seconds: parseInt(e.target.value) || 120 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
            <p className="mt-1 text-xs text-gray-500">How long image request tokens are valid (60-300 seconds)</p>
          </div>

          {!connector && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-gray-700">Public Key (PEM)</label>
                <button
                  type="button"
                  onClick={handleGenerateKeys}
                  disabled={isGenerating}
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  {isGenerating ? 'Generating...' : 'Generate Key Pair'}
                </button>
              </div>
              <textarea
                required
                rows={6}
                value={formData.public_key_pem}
                onChange={(e) => setFormData({ ...formData, public_key_pem: e.target.value })}
                placeholder="-----BEGIN PUBLIC KEY-----&#10;...&#10;-----END PUBLIC KEY-----"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-xs"
              />

              {generatedKeys && (
                <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center text-amber-800">
                      <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                      <span className="font-medium">Save the Private Key!</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(generatedKeys.private_key_pem)}
                      className="text-sm text-amber-700 hover:text-amber-900 flex items-center"
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 mr-1" />
                      Copy
                    </button>
                  </div>
                  <p className="text-xs text-amber-700 mb-2">
                    Configure this private key on your connector. It will not be shown again.
                  </p>
                  <pre className="text-xs bg-white p-2 rounded border border-amber-200 overflow-x-auto max-h-32">
                    {generatedKeys.private_key_pem}
                  </pre>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : connector ? 'Update' : 'Create Connector'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function KeyManagementModal({
  connector,
  onClose,
}: {
  connector: ImageConnector;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [showRotate, setShowRotate] = useState(false);
  const [newPublicKey, setNewPublicKey] = useState('');
  const [overlapHours, setOverlapHours] = useState(24);
  const [generatedKeys, setGeneratedKeys] = useState<{ private_key_pem: string; public_key_pem: string } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const rotateMutation = useMutation({
    mutationFn: (data: { new_public_key_pem: string; overlap_hours: number }) =>
      imageConnectorApi.rotateKey(connector.connector_id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-connectors'] });
      onClose();
    },
  });

  const handleGenerateKeys = async () => {
    setIsGenerating(true);
    try {
      const keys = await imageConnectorApi.generateKeypair();
      setGeneratedKeys(keys);
      setNewPublicKey(keys.public_key_pem);
    } catch (err) {
      console.error('Failed to generate keys:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleRotate = () => {
    rotateMutation.mutate({ new_public_key_pem: newPublicKey, overlap_hours: overlapHours });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Key Management</h3>
          <p className="text-sm text-gray-500">{connector.name}</p>
        </div>

        <div className="p-6 space-y-6">
          {/* Current Key Info */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Current Key</h4>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Key ID:</span>
                <span className="font-mono">{connector.public_key_id}</span>
              </div>
              {connector.public_key_expires_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Expires:</span>
                  <span>{format(new Date(connector.public_key_expires_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
              )}
              {connector.secondary_public_key_id && (
                <>
                  <div className="border-t border-gray-200 my-2 pt-2">
                    <span className="text-xs text-amber-600 font-medium">Key rotation in progress</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Secondary Key ID:</span>
                    <span className="font-mono">{connector.secondary_public_key_id}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Rotate Key Section */}
          {!showRotate ? (
            <button
              onClick={() => setShowRotate(true)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              <KeyIcon className="h-5 w-5 inline mr-2" />
              Rotate Public Key
            </button>
          ) : (
            <div className="border border-gray-200 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-gray-900">Rotate Key</h4>
                <button
                  type="button"
                  onClick={handleGenerateKeys}
                  disabled={isGenerating}
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  {isGenerating ? 'Generating...' : 'Generate New Key Pair'}
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Public Key (PEM)</label>
                <textarea
                  rows={6}
                  value={newPublicKey}
                  onChange={(e) => setNewPublicKey(e.target.value)}
                  placeholder="-----BEGIN PUBLIC KEY-----&#10;...&#10;-----END PUBLIC KEY-----"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-xs"
                />
              </div>

              {generatedKeys && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center text-amber-800">
                      <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                      <span className="font-medium">Save the Private Key!</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(generatedKeys.private_key_pem)}
                      className="text-sm text-amber-700 hover:text-amber-900 flex items-center"
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 mr-1" />
                      Copy
                    </button>
                  </div>
                  <p className="text-xs text-amber-700 mb-2">
                    Configure this private key on your connector before completing the rotation.
                  </p>
                  <pre className="text-xs bg-white p-2 rounded border border-amber-200 overflow-x-auto max-h-32">
                    {generatedKeys.private_key_pem}
                  </pre>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Overlap Period (hours)</label>
                <input
                  type="number"
                  min={1}
                  max={168}
                  value={overlapHours}
                  onChange={(e) => setOverlapHours(parseInt(e.target.value) || 24)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Both old and new keys will be accepted during this period (1-168 hours)
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowRotate(false);
                    setNewPublicKey('');
                    setGeneratedKeys(null);
                  }}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRotate}
                  disabled={!newPublicKey || rotateMutation.isPending}
                  className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {rotateMutation.isPending ? 'Rotating...' : 'Rotate Key'}
                </button>
              </div>

              {rotateMutation.error && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                  {(rotateMutation.error as any)?.response?.data?.detail || 'Failed to rotate key'}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// System Metrics Component
// ============================================================================

function SystemMetricsAdmin() {
  const { data: systemStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => systemApi.getStatus(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: demoMode } = useQuery({
    queryKey: ['demo-mode'],
    queryFn: () => systemApi.getDemoMode(),
  });

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => reportsApi.getDashboard(),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: throughput } = useQuery({
    queryKey: ['throughput', 7],
    queryFn: () => reportsApi.getThroughput(7),
  });

  const { data: reviewerPerformance } = useQuery({
    queryKey: ['reviewer-performance', 30],
    queryFn: () => reportsApi.getReviewerPerformance(30),
  });

  if (statusLoading || dashboardLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* System Status Card */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Environment</p>
            <p className="text-lg font-semibold text-gray-900 capitalize">
              {systemStatus?.environment || 'Unknown'}
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Version</p>
            <p className="text-lg font-semibold text-gray-900">
              {systemStatus?.version || '1.0.0'}
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Demo Mode</p>
            <p className={clsx(
              'text-lg font-semibold',
              systemStatus?.demo_mode_enabled ? 'text-amber-600' : 'text-green-600'
            )}>
              {systemStatus?.demo_mode_enabled ? 'Enabled' : 'Disabled'}
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-500">Database</p>
            <p className="text-lg font-semibold text-green-600">
              {systemStatus?.database_type || 'PostgreSQL'}
            </p>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-sm text-blue-600">Pending Items</p>
            <p className="text-2xl font-bold text-blue-700">
              {dashboard?.pending_items || 0}
            </p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg border border-green-100">
            <p className="text-sm text-green-600">Approved Today</p>
            <p className="text-2xl font-bold text-green-700">
              {dashboard?.approved_today || 0}
            </p>
          </div>
          <div className="p-4 bg-red-50 rounded-lg border border-red-100">
            <p className="text-sm text-red-600">Rejected Today</p>
            <p className="text-2xl font-bold text-red-700">
              {dashboard?.rejected_today || 0}
            </p>
          </div>
          <div className="p-4 bg-amber-50 rounded-lg border border-amber-100">
            <p className="text-sm text-amber-600">Escalated</p>
            <p className="text-2xl font-bold text-amber-700">
              {dashboard?.escalated_items || 0}
            </p>
          </div>
        </div>
      </div>

      {/* Throughput Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">7-Day Throughput</h2>
          {throughput?.daily_stats ? (
            <div className="space-y-3">
              {throughput.daily_stats.slice(-7).map((day: any, index: number) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{day.date}</span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium text-gray-900">
                      {day.total_reviewed || 0} reviewed
                    </span>
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-primary-600 h-2 rounded-full"
                        style={{ width: `${Math.min((day.total_reviewed || 0) / 50 * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No throughput data available</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Reviewer Performance</h2>
          {reviewerPerformance?.reviewers ? (
            <div className="space-y-3">
              {reviewerPerformance.reviewers.slice(0, 5).map((reviewer: any, index: number) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{reviewer.username}</span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium text-gray-900">
                      {reviewer.total_decisions || 0} decisions
                    </span>
                    <span className="text-xs text-gray-500">
                      {reviewer.avg_time_seconds ? `${Math.round(reviewer.avg_time_seconds)}s avg` : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No reviewer data available</p>
          )}
        </div>
      </div>

      {/* Queue Summary */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Queue Summary</h2>
        {dashboard?.queue_summary ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Queue</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Pending</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">In Progress</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Completed Today</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {dashboard.queue_summary.map((queue: any, index: number) => (
                  <tr key={index}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{queue.name}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{queue.pending || 0}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{queue.in_progress || 0}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{queue.completed_today || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No queue data available</p>
        )}
      </div>

      {/* Demo Mode Info (if enabled) */}
      {demoMode?.enabled && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-amber-800 mb-2">Demo Mode Active</h2>
          <ul className="space-y-1">
            {demoMode.notices?.map((notice: string, index: number) => (
              <li key={index} className="text-sm text-amber-700">• {notice}</li>
            ))}
          </ul>
          <div className="mt-4 pt-4 border-t border-amber-200">
            <p className="text-sm text-amber-700">
              Demo Data Count: <span className="font-semibold">{demoMode.demo_data_count}</span> items
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Admin Page Component
// ============================================================================

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
                      location.pathname === item.href || location.pathname.startsWith(item.href + '/')
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
            <Route path="/" element={<SystemMetricsAdmin />} />
            <Route path="/metrics" element={<SystemMetricsAdmin />} />
            <Route path="/users" element={<UsersAdmin />} />
            <Route path="/queues" element={<QueuesAdmin />} />
            <Route path="/policies" element={<PoliciesAdmin />} />
            <Route path="/connectors" element={<ImageConnectorsAdmin />} />
            <Route path="/audit" element={<AuditLogAdmin />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
