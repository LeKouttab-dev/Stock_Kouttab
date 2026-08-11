import { create } from 'zustand';

export type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant: ToastVariant;
  duration: number;
}

interface ToastStore {
  toasts: Toast[];
  push: (toast: Omit<Toast, 'id' | 'duration'> & { duration?: number }) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: ({ duration = 4000, ...rest }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const toast: Toast = { id, duration, ...rest };
    set((s) => ({ toasts: [...s.toasts, toast] }));
    if (duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
      }, duration);
    }
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

export function useToast() {
  const push = useToastStore((s) => s.push);
  const dismiss = useToastStore((s) => s.dismiss);
  return {
    toast: (opts: Parameters<typeof push>[0]) => push(opts),
    success: (title: string, description?: string) =>
      push({ title, description, variant: 'success' }),
    error: (title: string, description?: string) => push({ title, description, variant: 'error' }),
    warning: (title: string, description?: string) =>
      push({ title, description, variant: 'warning' }),
    info: (title: string, description?: string) => push({ title, description, variant: 'info' }),
    dismiss,
  };
}

export function useToastList(): Toast[] {
  return useToastStore((s) => s.toasts);
}

/** Vide la file de toasts. Utilisé essentiellement dans les tests. */
export function resetToasts(): void {
  useToastStore.getState().clear();
}
