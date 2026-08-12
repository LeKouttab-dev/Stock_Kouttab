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
];

vi.mock('@/api/endpoints/expenses', () => ({
  useAllExpenses: () => ({ data: notes, isLoading: false }),
  useValidateExpense: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteExpense: () => ({ mutate: vi.fn(), isPending: false }),
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
  reimbursementQueryKeys: { all: ['reimbursements'] },
}));

import { ValidateExpensesPage } from '../ValidateExpensesPage';

describe('pages/expenses/ValidateExpensesPage', () => {
  it('affiche un bénévole par fiche, et non une note par ligne', () => {
    renderWithProviders(<ValidateExpensesPage />);

    expect(screen.getByText('Omar Benfdila')).toBeInTheDocument();
    expect(screen.getByText('Autre Bénévole')).toBeInTheDocument();
    expect(screen.getByText('3 note(s)')).toBeInTheDocument();
  });

  it('annonce ce qui reste dû, avances déduites', () => {
    renderWithProviders(<ValidateExpensesPage />);
    // 30 + (20 - 5) = 45 ; la note « En attente » n'est pas encore due.
    expect(screen.getByText(/45,00/)).toBeInTheDocument();
  });

  it('ne propose au remboursement que les notes approuvées', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    await user.click(screen.getByText('Omar Benfdila'));

    const cases = await screen.findAllByRole('checkbox');
    // 1 case « tout sélectionner » + 3 notes du bénévole.
    const casesNotes = cases.slice(1);
    expect(casesNotes).toHaveLength(3);
    // Celle de la note « En attente » est inerte : l'API la refuserait.
    expect(casesNotes.filter((c) => (c as HTMLInputElement).disabled)).toHaveLength(1);
  });

  it("fait apparaître l'action de remboursement à la première sélection", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    await user.click(screen.getByText('Omar Benfdila'));
    expect(screen.queryByRole('button', { name: /Rembourser/ })).not.toBeInTheDocument();

    const cases = await screen.findAllByRole('checkbox');
    await user.click(cases[1]);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Rembourser/ })).toBeInTheDocument(),
    );
  });

  it('un bénévole sans note approuvée ne propose aucune sélection', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ValidateExpensesPage />);

    await user.click(screen.getByText('Autre Bénévole'));

    expect(screen.queryByText(/Tout sélectionner/)).not.toBeInTheDocument();
  });
});
