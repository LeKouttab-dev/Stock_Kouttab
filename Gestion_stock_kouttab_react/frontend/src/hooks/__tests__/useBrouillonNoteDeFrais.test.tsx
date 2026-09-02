import { act, renderHook, waitFor } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Le brouillon de note de frais : ce qu'il garde, et ce qu'il refuse de rendre.
 *
 * Le bénévole sans RIB est renvoyé vers son profil au milieu de sa saisie, et
 * l'onglet qu'il quitte est démonté par Radix. Sans ce brouillon, il retrouvait
 * un formulaire vide et devait tout ressaisir — le contraire du service rendu.
 *
 * Ce qui casse le plus facilement : la restauration d'un brouillon écrit par une
 * version antérieure du formulaire, ou vieux de plusieurs mois. Rendre n'importe
 * quoi est pire que ne rien rendre.
 */

import { CLE_BROUILLON_NDF, useBrouillonNoteDeFrais } from '../useBrouillonNoteDeFrais';

const UTILISATEUR = 7;

interface Valeurs {
  fournisseur: string;
  montant: number;
}

const VIDE: Valeurs = { fournisseur: '', montant: 0 };

function cle(userId: number = UTILISATEUR) {
  return `${CLE_BROUILLON_NDF}.${userId}`;
}

function monterFormulaire(actif = true) {
  return renderHook(() => {
    const form = useForm<Valeurs>({ defaultValues: VIDE });
    const brouillon = useBrouillonNoteDeFrais(form, { userId: UTILISATEUR, actif });
    return { form, brouillon };
  });
}

describe('hooks/useBrouillonNoteDeFrais', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it('relit la saisie après un démontage du formulaire', async () => {
    const premier = monterFormulaire();
    act(() => premier.result.current.form.setValue('fournisseur', 'Carrefour'));
    await waitFor(() => expect(localStorage.getItem(cle())).toBeTruthy());
    premier.unmount();

    const second = monterFormulaire();

    await waitFor(() =>
      expect(second.result.current.form.getValues('fournisseur')).toBe('Carrefour'),
    );
  });

  it('ignore un brouillon écrit par une version antérieure du formulaire', async () => {
    localStorage.setItem(
      cle(),
      JSON.stringify({ version: 0, enregistre_le: Date.now(), valeurs: { fournisseur: 'Vieux' } }),
    );

    const { result } = monterFormulaire();

    await waitFor(() => expect(result.current.brouillon.restaure).toBe(false));
    expect(result.current.form.getValues('fournisseur')).toBe('');
  });

  it('ignore un brouillon trop ancien', async () => {
    const ilYA8Jours = Date.now() - 8 * 24 * 60 * 60 * 1000;
    localStorage.setItem(
      cle(),
      JSON.stringify({ version: 1, enregistre_le: ilYA8Jours, valeurs: { fournisseur: 'Vieux' } }),
    );

    const { result } = monterFormulaire();

    await waitFor(() => expect(result.current.brouillon.restaure).toBe(false));
    expect(result.current.form.getValues('fournisseur')).toBe('');
  });

  it('ne rend pas le brouillon d’un autre compte', async () => {
    localStorage.setItem(
      cle(99),
      JSON.stringify({ version: 1, enregistre_le: Date.now(), valeurs: { fournisseur: 'Autre' } }),
    );

    const { result } = monterFormulaire();

    await waitFor(() => expect(result.current.brouillon.restaure).toBe(false));
    expect(result.current.form.getValues('fournisseur')).toBe('');
  });

  it('efface le brouillon quand la note est envoyée', async () => {
    const { result } = monterFormulaire();
    act(() => result.current.form.setValue('fournisseur', 'Carrefour'));
    await waitFor(() => expect(localStorage.getItem(cle())).toBeTruthy());

    act(() => result.current.brouillon.effacer());

    expect(localStorage.getItem(cle())).toBeNull();
  });

  it('survit à un stockage indisponible', async () => {
    // Navigation privée, quota atteint : le formulaire doit continuer de
    // fonctionner sans brouillon plutôt que de casser à la frappe.
    const setItem = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('QuotaExceededError');
      });

    const { result } = monterFormulaire();
    act(() => result.current.form.setValue('fournisseur', 'Carrefour'));

    await waitFor(() => expect(result.current.form.getValues('fournisseur')).toBe('Carrefour'));
    setItem.mockRestore();
  });

  it('n’écrit rien tant que le brouillon est désactivé', async () => {
    const { result } = monterFormulaire(false);

    act(() => result.current.form.setValue('fournisseur', 'Carrefour'));

    await new Promise((r) => setTimeout(r, 50));
    expect(localStorage.getItem(cle())).toBeNull();
  });
});
