import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { Expense } from '@/types/api';

/**
 * L'écran comptable regroupe par bénévole, parce que c'est une personne qu'on
 * rembourse, pas une note. Ces tests portent sur ce que le regroupement change
 * pour le comptable : ce qu'il voit, et ce qu'il peut sélectionner.
 */

const supprimer = vi.fn();
let estSuperAdmin = true;

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ can: () => estSuperAdmin }),
}));

const notes: Expense[] = [
  {
    id: 1,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    date_depense: '2026-08-03',
    montant: 30,
    remboursement_deja_emis: 0,
    remise: 0,
    status: 'Approuvée',
    fournisseur: 'Metro',
  } as Expense,
  {
    id: 2,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    date_depense: '2026-08-04',
    montant: 20,
    remboursement_deja_emis: 5,
    remise: 0,
    status: 'Approuvée',
  } as Expense,
  {
    id: 3,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    date_depense: '2026-08-05',
    montant: 99,
    remboursement_deja_emis: 0,
    remise: 0,
    status: 'En attente',
  } as Expense,
  {
    id: 4,
    id_user: 9,
    user_full_name: 'Autre Bénévole',
    date_depense: '2026-08-01',
    montant: 10,
    remboursement_deja_emis: 0,
    remise: 0,
    status: 'Remboursée',
  } as Expense,
  {
    id: 6,
    id_user: 11,
    user_full_name: 'Ancienne Note',
    date_depense: '2024-03-04',
    montant: 8,
    remboursement_deja_emis: 0,
    remise: 0,
    // Écriture de la version Streamlit : sans accent.
    status: 'Refusee',
  } as unknown as Expense,
  {
    id: 5,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    date_depense: '2026-05-02',
    montant: 12,
    remboursement_deja_emis: 0,
    remise: 0,
    status: 'Remboursée',
    archived_at: '2026-06-01T10:00:00',
    archived_by_name: 'Compta',
  } as Expense,
];

vi.mock('@/api/endpoints/expenses', () => ({
  useAllExpenses: () => ({ data: notes, isLoading: false }),
  useValidateExpense: () => ({ mutate: vi.fn(), isPending: false }),
  useArchiveExpense: () => ({ mutate: vi.fn(), isPending: false }),
  useSupprimerDefinitivement: () => ({ mutate: supprimer, isPending: false }),
  useRestoreExpense: () => ({ mutate: vi.fn(), isPending: false }),
  expenseQueryKeys: { all: ['expenses'] },
}));
vi.mock('@/api/endpoints/reimbursements', () => ({
  useReimbursementOptions: () => ({
    data: {
      moyens: ['Virement bancaire'],
      etablissements: ['Wise'],
      moyen_defaut: 'Virement bancaire',
      etablissement_defaut: 'Wise',
      approbateur_defaut: 'DTC',
    },
  }),
  useCreateReimbursement: () => ({ mutate: vi.fn(), isPending: false }),
  // Aucun versement enregistré : c'est le cas des notes marquées
  // « Remboursée » par l'ancienne liste déroulante.
  useRemboursementParNote: () => new Map(),
  reimbursementDocumentPath: (id: number, format: string) =>
    `/reimbursements/${id}/document?format=${format}`,
  reimbursementQueryKeys: { all: ['reimbursements'] },
}));

import { ValidateExpensesPage } from '../ValidateExpensesPage';

/** Les vues antérieures aux filtres se lisent désormais sous « Toutes ». */
async function toutAfficher(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: /Toutes/ }));
}

describe('pages/expenses/ValidateExpensesPage', () => {
  it('ouvre sur ce qui demande une action : à valider ET à payer', () => {
    renderWithProviders(<ValidateExpensesPage />);

    // 2 approuvées + 1 en attente pour Omar. Les notes approuvées font partie
    // du travail du jour : sans elles, le bouton « Rembourser » n'apparaissait
    // nulle part sur l'écran d'accueil.
    expect(screen.getByText('3 note(s)')).toBeInTheDocument();
    // La note déjà remboursée d'un autre bénévole reste hors du champ.
    expect(screen.queryByText('Autre Bénévole')).not.toBeInTheDocument();
  });

  it('propose le remboursement sans changer de filtre', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    await user.click(screen.getByText('Omar Benfdila'));
    const cases = await screen.findAllByRole('checkbox');
    await user.click(cases[1]);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Rembourser/ })).toBeInTheDocument(),
    );
  });

  it('annonce ce qui est dû quel que soit le filtre consulté', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    // La somme due à quelqu'un ne dépend pas de l'écran qu'on regarde : elle
    // tombait à zéro dès qu'on changeait d'onglet.
    await user.click(screen.getByRole('tab', { name: /Toutes/ }));
    expect(screen.getByText(/45,00/)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Approuvées/ }));
    expect(screen.getByText(/45,00/)).toBeInTheDocument();
  });

  it('ouvre le formulaire sur la valeur qu’il va réellement envoyer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await user.click(screen.getByRole('tab', { name: /Remboursées/ }));
    await user.click(screen.getByText('Autre Bénévole'));
    await user.click(screen.getByText(/01\/08\/2026/));

    // L'écran affichait « Approuvée » en gardant « Remboursée » dans le
    // formulaire : « Mettre à jour » renvoyait le statut inchangé, le serveur
    // l'acceptait comme un non-changement, et le message de succès s'affichait
    // alors que rien n'avait bougé.
    const liste = await screen.findByRole('combobox');
    expect(liste).toHaveTextContent('Approuvée');
  });

  it('donne accès à l’historique par les filtres', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    await user.click(screen.getByRole('tab', { name: /Remboursées/ }));
    expect(screen.getByText('Autre Bénévole')).toBeInTheDocument();
  });

  it('range les notes archivées dans leur propre filtre', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    // Absente du courant : c'est tout l'objet de l'archivage. Omar n'a pas
    // d'autre note remboursée, sa fiche disparaît donc entièrement de la vue.
    await user.click(screen.getByRole('tab', { name: /Remboursées/ }));
    expect(screen.queryByText('Omar Benfdila')).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Archivées/ }));
    await user.click(screen.getByText('Omar Benfdila'));
    expect(await screen.findByText(/02\/05\/2026/)).toBeInTheDocument();
  });

  it('affiche un bénévole par fiche, et non une note par ligne', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);

    expect(screen.getByText('Omar Benfdila')).toBeInTheDocument();
    expect(screen.getByText('Autre Bénévole')).toBeInTheDocument();
    expect(screen.getByText('4 note(s)')).toBeInTheDocument();
  });

  it('annonce ce qui reste dû, avances déduites', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);
    // 30 + (20 - 5) = 45 ; la note « En attente » n'est pas encore due.
    expect(screen.getByText(/45,00/)).toBeInTheDocument();
  });

  it('ne propose au remboursement que les notes approuvées', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);

    await user.click(screen.getByText('Omar Benfdila'));

    const cases = await screen.findAllByRole('checkbox');
    // 1 case « tout sélectionner » + 4 notes du bénévole.
    const casesNotes = cases.slice(1);
    expect(casesNotes).toHaveLength(4);
    // Inertes : la note « En attente », que l'API refuserait, et l'archivée.
    expect(casesNotes.filter((c) => (c as HTMLInputElement).disabled)).toHaveLength(2);
  });

  it("fait apparaître l'action de remboursement à la première sélection", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);

    await user.click(screen.getByText('Omar Benfdila'));
    expect(screen.queryByRole('button', { name: /Rembourser/ })).not.toBeInTheDocument();

    const cases = await screen.findAllByRole('checkbox');
    await user.click(cases[1]);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Rembourser/ })).toBeInTheDocument(),
    );
  });

  it('ne propose plus de déclarer une note « Remboursée »', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);
    await user.click(screen.getByText('Omar Benfdila'));
    await user.click(screen.getByText(/03\/08\/2026/));

    // Le choix produisait une note payée sans justificatif, dans un état
    // terminal impossible à corriger. Le bouton « Rembourser » fait les deux.
    const liste = await screen.findByRole('combobox');
    await user.click(liste);
    expect(screen.queryByRole('option', { name: 'Remboursée' })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Approuvée' })).toBeInTheDocument();
  });

  it('signale une note remboursée sans versement enregistré', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await user.click(screen.getByRole('tab', { name: /Remboursées/ }));
    await user.click(screen.getByText('Autre Bénévole'));
    await user.click(screen.getByText(/01\/08\/2026/));

    // Chercher un PDF qui n'a jamais existé est pire que de le dire.
    expect(await screen.findByText(/sans versement enregistré/)).toBeInTheDocument();
  });

  it('ouvre le formulaire d’une note héritée sur un statut exploitable', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);
    await user.click(screen.getByText('Ancienne Note'));
    await user.click(screen.getByText(/04\/03\/2024/));

    // Avec « Refusee » tel quel, le schéma du formulaire refusait la
    // soumission : « Mettre à jour » ne partait jamais, sans message. Les
    // anciennes notes étaient donc impossibles à corriger.
    const liste = await screen.findByRole('combobox');
    expect(liste).toHaveTextContent('Refusée');
  });

  it('exige un motif avant de supprimer définitivement', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await user.click(screen.getByText('Omar Benfdila'));
    await user.click(screen.getByText(/03\/08\/2026/));

    await user.click(await screen.findByRole('button', { name: /Supprimer définitivement/ }));

    // Le geste est irréversible : le bouton reste inerte tant que rien n'est
    // écrit. Quelqu'un qui doit dire pourquoi il supprime relit ce qu'il
    // supprime.
    const confirmer = await screen.findByRole('button', { name: /Je comprends/ });
    expect(confirmer).toBeDisabled();
    expect(screen.getByText(/irrévocable/)).toBeInTheDocument();
    // Dit deux fois, volontairement : sous le bouton avant le clic, et dans
    // la fenêtre au moment de confirmer.
    expect(screen.getAllByText(/jamais une note de frais réelle/)).toHaveLength(2);

    await user.type(screen.getByLabelText(/Motif/), 'Note de recette');
    await waitFor(() => expect(confirmer).toBeEnabled());
    await user.click(confirmer);

    await waitFor(() => expect(supprimer).toHaveBeenCalled());
    expect(supprimer.mock.calls[0][0]).toMatchObject({ motif: 'Note de recette' });
  });

  it('cache la suppression à qui n’est pas Super Admin', async () => {
    const user = userEvent.setup();
    estSuperAdmin = false;
    renderWithProviders(<ValidateExpensesPage />);
    await user.click(screen.getByText('Omar Benfdila'));
    await user.click(screen.getByText(/03\/08\/2026/));

    expect(
      screen.queryByRole('button', { name: /Supprimer définitivement/ }),
    ).not.toBeInTheDocument();
    estSuperAdmin = true;
  });

  it('un bénévole sans note approuvée ne propose aucune sélection', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);
    await toutAfficher(user);

    await user.click(screen.getByText('Autre Bénévole'));

    expect(screen.queryByText(/Tout sélectionner/)).not.toBeInTheDocument();
  });
});
