import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';

/**
 * Écarter un justificatif : le motif est obligatoire.
 *
 * Il est lu par le déposant, et c'est lui qui doit savoir quoi redéposer. Sans
 * explication, il renvoie la même pièce et le va-et-vient recommence — d'où un
 * champ exigé plutôt qu'une simple confirmation.
 */

const ecarter = vi.fn();

vi.mock('@/api/endpoints/expenses', () => ({
  useEcarterJustificatif: () => ({ mutate: ecarter, isPending: false }),
  expenseQueryKeys: { all: ['expenses'] },
}));

import { EcartJustificatifModal } from '../modals/EcartJustificatifModal';

describe('pages/expenses/EcartJustificatifModal', () => {
  it('exige un motif avant d’écarter', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <EcartJustificatifModal expenseId={12} fileId={34} onClose={vi.fn()} />,
    );

    const confirmer = await screen.findByRole('button', { name: /^Écarter$/ });
    expect(confirmer).toBeDisabled();

    await user.type(screen.getByLabelText(/Pourquoi cette pièce/), 'Montant illisible');
    await waitFor(() => expect(confirmer).toBeEnabled());
    await user.click(confirmer);

    await waitFor(() => expect(ecarter).toHaveBeenCalled());
    expect(ecarter.mock.calls[0][0]).toMatchObject({
      expenseId: 12,
      fileId: 34,
      motif: 'Montant illisible',
    });
  });

  it('reste fermée tant qu’aucune pièce n’est visée', () => {
    renderWithProviders(
      <EcartJustificatifModal expenseId={12} fileId={null} onClose={vi.fn()} />,
    );
    expect(screen.queryByRole('button', { name: /^Écarter$/ })).not.toBeInTheDocument();
  });

  it('annonce que le geste se défait', async () => {
    renderWithProviders(
      <EcartJustificatifModal expenseId={12} fileId={34} onClose={vi.fn()} />,
    );
    // Pas d'avertissement alarmant : contrairement à la suppression d'une note,
    // écarter une pièce se rétablit.
    expect(await screen.findByText(/peut être rétablie/)).toBeInTheDocument();
  });
});
