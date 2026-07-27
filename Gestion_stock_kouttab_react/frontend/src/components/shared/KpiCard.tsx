import { type ReactNode } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  hint?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
}

/**
 * Tons KPI alignés sur la charte "Le Kouttâb" :
 *   default → terracotta (valeur principale, accent chaleureux)
 *   success → sage foncé (vert "OK")
 *   warning → terracotta (action requise, mais reste chaleureux)
 *   danger  → rouge système
 *   info    → forest (vert profond, neutre informatif)
 */
const tones: Record<NonNullable<KpiCardProps['variant']>, string> = {
  default: 'text-terracotta-700',
  success: 'text-sage-700',
  warning: 'text-terracotta-600',
  danger: 'text-red-700',
  info: 'text-forest-700',
};

export function KpiCard({ label, value, icon, hint, variant = 'default', className }: KpiCardProps) {
  return (
    <Card className={cn('border-border bg-card', className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className={cn('mt-2 text-2xl font-bold font-serif', tones[variant])}>{value}</p>
            {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
          </div>
          {icon && <div className={cn('opacity-80', tones[variant])}>{icon}</div>}
        </div>
      </CardContent>
    </Card>
  );
}
