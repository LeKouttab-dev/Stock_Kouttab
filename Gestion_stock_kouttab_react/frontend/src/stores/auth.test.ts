import { describe, expect, it, beforeEach } from 'vitest';
import { useAuthStore } from './auth';
import type { User } from '@/types/api';

const fakeUser: User = {
  id: 1,
  username: 'alice',
  role: 'Compta',
  validation_status: 'active',
  nom: 'A',
  prenom: 'Alice',
  email: 'a@a.fr',
};

describe('stores/auth', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
  });

  it('starts with empty state', () => {
    const s = useAuthStore.getState();
    expect(s.user).toBeNull();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.isAuthenticated()).toBe(false);
  });

  it('setSession populates user + tokens', () => {
    useAuthStore.getState().setSession({
      user: fakeUser,
      accessToken: 'access',
      refreshToken: 'refresh',
    });
    const s = useAuthStore.getState();
    expect(s.user).toEqual(fakeUser);
    expect(s.accessToken).toBe('access');
    expect(s.refreshToken).toBe('refresh');
    expect(s.isAuthenticated()).toBe(true);
  });

  it('setUser updates only the user field', () => {
    useAuthStore.getState().setSession({
      user: fakeUser,
      accessToken: 'access',
      refreshToken: 'refresh',
    });
    const updated: User = { ...fakeUser, nom: 'NewName' };
    useAuthStore.getState().setUser(updated);
    expect(useAuthStore.getState().user?.nom).toBe('NewName');
    expect(useAuthStore.getState().accessToken).toBe('access');
  });

  it('logout resets to initial state', () => {
    useAuthStore.getState().setSession({
      user: fakeUser,
      accessToken: 'access',
      refreshToken: 'refresh',
    });
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.user).toBeNull();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
  });
});
