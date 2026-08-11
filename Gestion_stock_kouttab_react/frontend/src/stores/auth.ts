import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  setSession: (payload: { user: User; accessToken: string; refreshToken: string }) => void;
  setTokens: (payload: { accessToken: string; refreshToken?: string }) => void;
  setUser: (user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setSession: ({ user, accessToken, refreshToken }) => set({ user, accessToken, refreshToken }),
      setTokens: ({ accessToken, refreshToken }) =>
        set((s) => ({
          accessToken,
          refreshToken: refreshToken ?? s.refreshToken,
        })),
      setUser: (user) => set({ user }),
      logout: () => set({ user: null, accessToken: null, refreshToken: null }),
      isAuthenticated: () => Boolean(get().accessToken && get().user),
    }),
    {
      name: 'kouttab-auth',
      partialize: (s) => ({
        user: s.user,
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
      }),
    },
  ),
);
