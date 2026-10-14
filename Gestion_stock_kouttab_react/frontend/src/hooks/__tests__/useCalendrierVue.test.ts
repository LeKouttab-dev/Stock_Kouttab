import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCalendrierVue } from '@/hooks/useCalendrierVue';

function ecran(compact: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((requete: string) => ({
      matches: compact,
      media: requete,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  window.matchMedia = globalThis.matchMedia;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useCalendrierVue', () => {
  it('sur téléphone, « Semaine » sert la liste de la semaine', () => {
    ecran(true);
    const { result } = renderHook(() => useCalendrierVue());
    act(() => result.current.choisir('semaine'));
    expect(result.current.vue).toBe('liste');
    // La barre montre toujours « Semaine » comme choix actif.
    expect(result.current.choisie).toBe('semaine');
  });

  it('sur téléphone, 3 jours reste 3 jours', () => {
    ecran(true);
    const { result } = renderHook(() => useCalendrierVue());
    act(() => result.current.choisir('trois-jours'));
    expect(result.current.vue).toBe('trois-jours');
  });

  it('sur ordinateur, « Semaine » est la grille de la semaine', () => {
    ecran(false);
    const { result } = renderHook(() => useCalendrierVue());
    act(() => result.current.choisir('semaine'));
    expect(result.current.vue).toBe('semaine');
  });
});
