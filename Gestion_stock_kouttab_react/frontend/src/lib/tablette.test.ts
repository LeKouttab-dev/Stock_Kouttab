import { afterEach, describe, expect, it } from 'vitest';
import { useAuthStore } from '@/stores/auth';
import { mockUser } from '@/test/mocks/handlers';
import {
  activerModeTablette,
  lireFragmentTablette,
  operateurDuJeton,
  operateurMemorise,
  quitterModeTablette,
} from './tablette';

function jeton(charge: Record<string, unknown>): string {
  const octets = new TextEncoder().encode(JSON.stringify(charge));
  const base64 = btoa(String.fromCharCode(...octets))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  return `entete.${base64}.signature`;
}

afterEach(() => quitterModeTablette());

describe('lib/tablette', () => {
  it("lit l'ancre de la tablette", () => {
    expect(lireFragmentTablette('#access=a&refresh=r&op=Youssef%20B.')).toEqual({
      access: 'a',
      refresh: 'r',
      op: 'Youssef B.',
    });
    expect(lireFragmentTablette('#access=a&refresh=r')).toEqual({
      access: 'a',
      refresh: 'r',
      op: null,
    });
    expect(lireFragmentTablette('#access=a')).toBeNull();
    expect(lireFragmentTablette('')).toBeNull();
  });

  it('lit `op` dans un jeton (accents compris)', () => {
    expect(operateurDuJeton(jeton({ sub: '1', op: 'Aïcha' }))).toBe('Aïcha');
    expect(operateurDuJeton(jeton({ sub: '1' }))).toBeNull();
    expect(operateurDuJeton('pas-un-jeton')).toBeNull();
    expect(operateurDuJeton(null)).toBeNull();
  });

  it('la déconnexion quitte le mode tablette', () => {
    activerModeTablette('Youssef');
    expect(operateurMemorise()).toBe('Youssef');
    useAuthStore.setState({ user: mockUser, accessToken: 'a', refreshToken: 'r' });
    useAuthStore.getState().logout();
    expect(operateurMemorise()).toBeNull();
  });
});
