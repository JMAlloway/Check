import { Link } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';

/**
 * Small "back" affordance for sub-pages that are reached from a parent screen
 * (e.g. the Operations Hub) rather than the sidebar, so users have an in-page
 * way back instead of relying on the browser button.
 */
export default function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700"
    >
      <ArrowLeftIcon className="h-4 w-4 mr-1" aria-hidden="true" />
      {label}
    </Link>
  );
}
