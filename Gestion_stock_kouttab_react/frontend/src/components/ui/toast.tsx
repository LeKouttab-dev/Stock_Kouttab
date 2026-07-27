import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useToastList, useToast, type ToastVariant } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

const variantStyles: Record<ToastVariant, string> = {
  default: 'bg-card text-foreground border-border',
  success: 'bg-sage-50 text-forest-800 border-sage-300',
  error: 'bg-red-50 text-red-900 border-red-200',
  warning: 'bg-terracotta-50 text-terracotta-800 border-terracotta-200',
  info: 'bg-sand-50 text-forest-800 border-sand-300',
};

const icons: Record<ToastVariant, typeof Info> = {
  default: Info,
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

export function Toaster() {
  const toasts = useToastList();
  const { dismiss } = useToast();

  return (
    <div className="pointer-events-none fixed top-4 right-4 z-[100] flex flex-col gap-2 w-full max-w-sm">
      {toasts.map((t) => {
        const Icon = icons[t.variant];
        return (
          <div
            key={t.id}
            role="status"
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border p-4 shadow-lg animate-fade-in',
              variantStyles[t.variant],
            )}
          >
            <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              {t.title && <p className="font-semibold text-sm">{t.title}</p>}
              {t.description && <p className="text-sm opacity-90 mt-0.5">{t.description}</p>}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="opacity-70 hover:opacity-100 transition-opacity"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
