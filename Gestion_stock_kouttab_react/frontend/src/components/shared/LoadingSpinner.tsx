import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  className?: string;
  fullPage?: boolean;
}

const sizes = {
  sm: 'h-4 w-4',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
};

export function LoadingSpinner({
  size = 'md',
  label = 'Chargement…',
  className,
  fullPage,
}: LoadingSpinnerProps) {
  const spinner = (
    <div className={cn('flex flex-col items-center gap-3 text-muted-foreground', className)}>
      <div
        className={cn(
          'animate-spin rounded-full border-2 border-primary border-t-transparent',
          sizes[size],
        )}
      />
      {label && <p className="text-sm">{label}</p>}
    </div>
  );

  if (fullPage) {
    return <div className="flex min-h-[60vh] items-center justify-center">{spinner}</div>;
  }
  return spinner;
}
