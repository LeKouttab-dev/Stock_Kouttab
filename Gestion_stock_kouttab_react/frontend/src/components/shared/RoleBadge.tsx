import { Badge } from '@/components/ui/badge';
import { ROLE_COLORS, ROLE_LABELS, type Role } from '@/lib/constants';
import { cn } from '@/lib/utils';

export function RoleBadge({ role, className }: { role: Role; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        ROLE_COLORS[role],
        className,
      )}
    >
      {ROLE_LABELS[role]}
    </span>
  );
}

export function RoleBadgeFromString({ role, className }: { role: string; className?: string }) {
  return <Badge className={className}>{role}</Badge>;
}
