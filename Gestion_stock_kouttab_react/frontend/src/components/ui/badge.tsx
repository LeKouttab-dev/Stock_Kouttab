import { type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning';

const variants: Record<Variant, string> = {
  default: 'bg-primary text-primary-foreground border-transparent',
  secondary: 'bg-secondary text-secondary-foreground border-transparent',
  destructive: 'bg-destructive text-destructive-foreground border-transparent',
  outline: 'text-foreground',
  // success → sage (vert sauge clair, charte Kouttâb)
  success: 'bg-sage-200 text-forest-800 border-sage-300',
  // warning → terracotta clair (chaleureux, cohérent avec la charte)
  warning: 'bg-terracotta-100 text-terracotta-800 border-terracotta-200',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
