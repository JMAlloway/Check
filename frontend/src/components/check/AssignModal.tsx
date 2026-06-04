import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { checkApi, userApi, queueApi } from '../../services/api';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import type { CheckItem, Queue } from '../../types';

interface AssignableUser {
  id: string;
  username: string;
  full_name?: string;
  is_active: boolean;
  roles: string[];
}

interface AssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: CheckItem;
}

const REVIEWER_ROLES = ['reviewer', 'senior_reviewer', 'supervisor'];

export default function AssignModal({ isOpen, onClose, item }: AssignModalProps) {
  const queryClient = useQueryClient();
  const [reviewerId, setReviewerId] = useState(item.assigned_reviewer_id ?? '');
  const [queueId, setQueueId] = useState(item.queue_id ?? '');

  const { data: usersData } = useQuery({
    queryKey: ['users', 'assignable'],
    queryFn: () => userApi.getUsers({ page_size: 100, is_active: true }),
    enabled: isOpen,
  });
  const { data: queues } = useQuery({
    queryKey: ['queues'],
    queryFn: () => queueApi.getQueues(),
    enabled: isOpen,
  });

  const users: AssignableUser[] = (usersData?.items ?? []).filter((u: AssignableUser) =>
    u.roles?.some((r) => REVIEWER_ROLES.includes(r))
  );

  const assign = useMutation({
    mutationFn: () => {
      const payload: { reviewer_id?: string; queue_id?: string } = {};
      if (reviewerId && reviewerId !== item.assigned_reviewer_id) payload.reviewer_id = reviewerId;
      if (queueId && queueId !== item.queue_id) payload.queue_id = queueId;
      return checkApi.assignItem(item.id, payload);
    },
    onSuccess: () => {
      toast.success('Check reassigned');
      queryClient.invalidateQueries({ queryKey: ['checkItem', item.id] });
      queryClient.invalidateQueries({ queryKey: ['queues'] });
      onClose();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Failed to reassign');
    },
  });

  const trapRef = useFocusTrap<HTMLDivElement>(isOpen, onClose);

  if (!isOpen) return null;

  const changed =
    (reviewerId && reviewerId !== (item.assigned_reviewer_id ?? '')) ||
    (queueId && queueId !== (item.queue_id ?? ''));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Assign check"
    >
      <div ref={trapRef} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Assign check</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3">
          <label className="block text-sm">
            <span className="text-gray-700">Reviewer</span>
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.username} ({u.username})
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-gray-700">Queue</span>
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
              value={queueId}
              onChange={(e) => setQueueId(e.target.value)}
            >
              <option value="">Keep current</option>
              {(queues ?? []).map((q: Queue) => (
                <option key={q.id} value={q.id}>
                  {q.name}
                </option>
              ))}
            </select>
          </label>

          <button
            onClick={() => assign.mutate()}
            disabled={!changed || assign.isPending}
            className="w-full rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {assign.isPending ? 'Assigning…' : 'Save assignment'}
          </button>
        </div>
      </div>
    </div>
  );
}
