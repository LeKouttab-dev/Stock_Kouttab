import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Le rappel de connexion : ce qu'il dit, et surtout combien de fois.
 *
 * La règle qui casse le plus facilement est « une fois par session » : sans
 * elle, le rappel reparaît à chaque navigation et devient le bruit qu'une
 * notification est censée éviter.
 */

const toastInfo = vi.fn();
const resume = {
  notes_a_valider: 0,
  factures_a_traiter: 0,
  modifications_stock: 0,
  comptes_a_valider: 0,
  articles_en_alerte: 0,
  justificatifs_demandes: 0,
  tickets_ouverts: 0,
};
let utilisateur: { id: number; username: string; prenom?: string } | null = {
  id: 7,
  username: 'omar',
  prenom: 'Omar',
};

// `importOriginal` : le module exporte aussi `resetToasts`, dont se sert le
// setup global entre chaque test. Un mock qui ne rendrait que `useToast`
// ferait échouer toute la suite sur un import manquant.
vi.mock('@/hooks/useToast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/useToast')>()),
  useToast: () => ({ info: toastInfo, success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: utilisateur }),
}));
vi.mock('@/api/endpoints/notifications', () => ({
  usePendingSummary: () => ({ data: resume }),
}));

import { useRappelConnexion } from '../useRappelConnexion';

describe('hooks/useRappelConnexion', () => {
  beforeEach(() => {
    toastInfo.mockClear();
    sessionStorage.clear();
    Object.assign(resume, {
      notes_a_valider: 0,
      factures_a_traiter: 0,
      modifications_stock: 0,
      comptes_a_valider: 0,
      articles_en_alerte: 0,
      justificatifs_demandes: 0,
      tickets_ouverts: 0,
    });
    utilisateur = { id: 7, username: 'omar', prenom: 'Omar' };
  });

  it('annonce les dossiers en attente', async () => {
    resume.notes_a_valider = 3;
    resume.factures_a_traiter = 2;

    renderHook(() => useRappelConnexion());

    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));
    const [titre, detail] = toastInfo.mock.calls[0];
    expect(titre).toContain('Omar');
    expect(detail).toContain('3 note(s) de frais à valider');
    expect(detail).toContain('2 facture(s) à traiter');
  });

  it("ne dit rien quand il n'y a rien à traiter", async () => {
    renderHook(() => useRappelConnexion());
    await waitFor(() => expect(toastInfo).not.toHaveBeenCalled());
  });

  it('ne se répète pas à la navigation suivante', async () => {
    resume.notes_a_valider = 1;

    const premier = renderHook(() => useRappelConnexion());
    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));
    premier.unmount();

    renderHook(() => useRappelConnexion());
    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));
  });

  it('reparaît pour un autre utilisateur', async () => {
    resume.notes_a_valider = 1;

    renderHook(() => useRappelConnexion());
    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));

    utilisateur = { id: 9, username: 'autre' };
    renderHook(() => useRappelConnexion());
    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(2));
  });

  it('met en tête ce que la comptabilité me réclame', async () => {
    // Ce qu'on attend de moi passe avant ce que je dois traiter pour autrui.
    resume.justificatifs_demandes = 2;
    resume.notes_a_valider = 1;

    renderHook(() => useRappelConnexion());

    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));
    const detail = toastInfo.mock.calls[0][1] as string;
    expect(detail.indexOf('justificatif')).toBeLessThan(detail.indexOf('note(s) de frais'));
  });

  it('signale aussi le stock sous le seuil', async () => {
    resume.articles_en_alerte = 5;

    renderHook(() => useRappelConnexion());

    await waitFor(() => expect(toastInfo).toHaveBeenCalledTimes(1));
    expect(toastInfo.mock.calls[0][1]).toContain("5 article(s) sous le seuil d'alerte");
  });
});
