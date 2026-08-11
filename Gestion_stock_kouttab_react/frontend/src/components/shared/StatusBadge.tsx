import { STATUS_COLORS, STATUS_EMOJIS } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  withEmoji?: boolean;
  className?: string;
}

export function StatusBadge({ status, withEmoji = true, className }: StatusBadgeProps) {
  const colorClasses = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800 border-gray-200';
  const emoji = STATUS_EMOJIS[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        colorClasses,
        className,
      )}
    >
      {withEmoji && emoji && <span aria-hidden>{emoji}</span>}
      {status}
    </span>
  );
}
