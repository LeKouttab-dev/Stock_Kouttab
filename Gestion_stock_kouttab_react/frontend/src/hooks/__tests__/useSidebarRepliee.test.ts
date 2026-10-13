import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useSidebarRepliee } from '@/hooks/useSidebarRepliee';
import { estPleineLargeur } from '@/lib/layout';

/**
 * Le piège de « repliée par défaut sur le calendrier » est l'effet qui
 * re-replie à chaque navigation et se bat contre le clic de l'utilisateur.
 * L'état est donc dérivé, pas synchronisé — et c'est ce que vérifient les
 * deux derniers tests.
 */

beforeEach(() => localStorage.clear());

describe('estPleineLargeur', () => {
  it('ne vaut que pour le calendrier', () => {
    expect(estPleineLargeur('/calendar')).toBe(true);
    expect(estPleineLargeur('/calendar/quelque-chose')).toBe(true);
    expect(estPleineLargeur('/dashboard')).toBe(false);
    expect(estPleineLargeur('/calendarium')).toBe(false);
  });
});

describe('useSidebarRepliee', () => {
  it('se replie d’elle-même sur le calendrier, pas ailleurs', () => {
    expect(renderHook(() => useSidebarRepliee('/calendar')).result.current.repliee).toBe(true);
    expect(renderHook(() => useSidebarRepliee('/dashboard')).result.current.repliee).toBe(false);
  });

  it('une fois le choix exprimé, il vaut partout', () => {
    const { result } = renderHook(() => useSidebarRepliee('/calendar'));
    act(() => result.current.basculer());
    expect(result.current.repliee).toBe(false);
    // Et le calendrier ne le redéfait pas au prochain passage.
    expect(renderHook(() => useSidebarRepliee('/calendar')).result.current.repliee).toBe(false);
  });

  it('replier ailleurs vaut aussi partout', () => {
    const { result } = renderHook(() => useSidebarRepliee('/dashboard'));
    act(() => result.current.basculer());
    expect(renderHook(() => useSidebarRepliee('/dashboard')).result.current.repliee).toBe(true);
  });

  it('ne mémorise rien tant que personne n’a choisi', () => {
    renderHook(() => useSidebarRepliee('/calendar'));
    expect(localStorage.getItem('layout.sidebar')).toBeNull();
  });
});
