import { useAuthStore } from '@/stores/auth';
import { canAccess as canAccessFn, type Action } from '@/lib/auth';

export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const logout = useAuthStore((s) => s.logout);
  const isAuthenticated = Boolean(user && accessToken);

  const can = (action: Action) => canAccessFn(user?.role, action);

  return { user, accessToken, isAuthenticated, logout, can };
}
