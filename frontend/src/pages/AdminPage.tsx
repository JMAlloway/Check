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
  ChevronDownIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { userApi, queueAdminApi, policyApi, auditLogApi } from '../services/api';
import { format } from 'date-fns';

const adminNav = [
  { name: 'Users', href: '/admin/users', icon: UsersIcon },
  { name: 'Queues', href: '/admin/queues', icon: QueueListIcon },
  { name: 'Policies', href: '/admin/policies', icon: DocumentTextIcon },
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

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Policy Management</h2>
            <div className="text-sm text-gray-500">
              Policies define routing, escalation, and approval rules
            </div>
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
                No policies configured yet.
              </div>
            )}
          </div>
        )}
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
