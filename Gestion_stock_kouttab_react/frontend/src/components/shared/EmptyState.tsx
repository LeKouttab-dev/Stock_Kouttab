import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 py-12 text-center',
        className,
      )}
    >
      {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
      <h3 className="mb-1 text-base font-semibold">{title}</h3>
      {description && <p className="mb-4 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}
