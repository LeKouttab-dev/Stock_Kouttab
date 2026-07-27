import { type HTMLAttributes, forwardRef } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

type Variant = 'default' | 'destructive' | 'success' | 'warning' | 'info';

const variants: Record<Variant, string> = {
  default: 'bg-card text-foreground border-border',
  destructive: 'bg-red-50 text-red-900 border-red-200 [&>svg]:text-red-600',
  success: 'bg-sage-50 text-forest-800 border-sage-300 [&>svg]:text-sage-600',
  warning: 'bg-terracotta-50 text-terracotta-800 border-terracotta-200 [&>svg]:text-terracotta-600',
  info: 'bg-sand-50 text-forest-800 border-sand-300 [&>svg]:text-forest-600',
};

const icons: Record<Variant, typeof Info> = {
  default: Info,
  destructive: AlertCircle,
  success: CheckCircle2,
  warning: AlertTriangle,
  info: Info,
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  hideIcon?: boolean;
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'default', children, hideIcon, ...props }, ref) => {
    const Icon = icons[variant];
    return (
      <div
        ref={ref}
        role="alert"
        className={cn(
          'relative w-full rounded-lg border p-4 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg+div]:translate-y-[-3px] [&>svg~*]:pl-7',
          variants[variant],
          className,
        )}
        {...props}
      >
        {!hideIcon && <Icon className="h-4 w-4" />}
        {children}
      </div>
    );
  },
);
Alert.displayName = 'Alert';

export const AlertTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5
      ref={ref}
      className={cn('mb-1 font-medium leading-none tracking-tight', className)}
      {...props}
    />
  ),
);
AlertTitle.displayName = 'AlertTitle';

export const AlertDescription = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('text-sm [&_p]:leading-relaxed', className)} {...props} />
  ),
);
AlertDescription.displayName = 'AlertDescription';
