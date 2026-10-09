import { act } from '@testing-library/react';
import { useAuthStore } from '@/stores/auth';
import { mockUser } from '@/test/mocks/handlers';
import type { Role } from '@/lib/constants';

export const BASE_URL = 'http://localhost:8000/api/v1';

/** `renderWithProviders` vide le store d'auth : on connecte APRÈS le rendu. */
export function connecter(role: Role) {
  act(() => {
    useAuthStore.setState({ user: { ...mockUser, role }, accessToken: 'jeton' });
  });
}
