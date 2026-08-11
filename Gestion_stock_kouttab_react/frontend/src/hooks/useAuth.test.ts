import { describe, expect, it, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAuth } from './useAuth';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types/api';

const fakeUser: User = {
  id: 42,
  username: 'jane',
  role: 'Super Admin',
  validation_status: 'active',
  nom: 'Doe',
  prenom: 'Jane',
  email: 'jane@example.com',
};

describe('hooks/useAuth', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
  });

  it('reports isAuthenticated=false when no user/token', () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('exposes the user once a session is set', () => {
    const { result } = renderHook(() => useAuth());
    act(() => {
      useAuthStore.getState().setSession({
        user: fakeUser,
        accessToken: 'tok',
        refreshToken: 'ref',
      });
    });
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe('jane');
    // Super Admin can access everything
    expect(result.current.can('admin:validate_users')).toBe(true);
  });

  it('logout empties the store', () => {
    const { result } = renderHook(() => useAuth());
    act(() => {
      useAuthStore.getState().setSession({
        user: fakeUser,
        accessToken: 'tok',
        refreshToken: 'ref',
      });
    });
    act(() => {
      result.current.logout();
    });
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});
