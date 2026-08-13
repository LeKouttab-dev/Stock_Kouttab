import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { Invoice } from '@/types/api';

/**
 * Qui a déposé la facture ?
 *
 * La ligne « Déposée par » restait **vide** : l'écran lisait `prenom` et `nom`,
 * deux champs que l'API ne renvoie pas sur une facture — elle envoie
 * `user_full_name`. La comptabilité voyait donc des pièces sans savoir de qui
 * elles venaient.
 */

const archiver = vi.fn();

const factures: Invoice[] = [
  {
    id: 1,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    status: 'En attente',
    date_depot: '2026-08-12',
    files: [{ id: 1, nom_fichier: 'facture.pdf' }],
    pole: 'Frais généraux',
    categorie: 'Courses',
  } as Invoice,
  {
    id: 2,
    id_user: 7,
    user_full_name: 'Omar Benfdila',
    status: 'Validée',
    date_depot: '2026-07-02',
    files: [{ id: 2, nom_fichier: 'ancienne.pdf' }],
    archived_at: '2026-08-01T10:00:00',
    archived_by_name: 'Compta',
  } as Invoice,
];

vi.mock('@/api/endpoints/invoices', () => ({
  useInvoices: () => ({ data: factures, isLoading: false }),
  useUpdateInvoiceStatus: () => ({ mutate: vi.fn(), isPending: false }),
  useArchiverFacture: () => ({ mutate: archiver, isPending: false }),
  useRestaurerFacture: () => ({ mutate: vi.fn(), isPending: false }),
  useResendComptaEmail: () => ({ mutate: vi.fn(), isPending: false }),
  invoiceQueryKeys: { all: ['invoices'] },
}));
vi.mock('@/api/endpoints/tickets', () => ({
  useTickets: () => ({ data: [], isLoading: false }),
  useTicketRecipients: () => ({ data: [] }),
  useCreateTicket: () => ({ mutate: vi.fn(), isPending: false }),
  useCloseTicket: () => ({ mutate: vi.fn(), isPending: false }),
  useRemindTicket: () => ({ mutate: vi.fn(), isPending: false }),
  ticketQueryKeys: { all: ['tickets'] },
}));

import { InvoiceListPage } from '../InvoiceListPage';

describe('pages/invoices/InvoiceListPage', () => {
  it('nomme le déposant de la facture', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InvoiceListPage />);

    // L'en-tête ne porte que le numéro et la date : le nom du déposant n'est
    // visible qu'une fois le détail ouvert.
    expect(screen.queryByText(/Omar Benfdila/)).not.toBeInTheDocument();
    await user.click(screen.getByText(/Facture #1/));

    // On vérifie la ligne elle-même, et non la simple présence du nom quelque
    // part : avec le bug, ce libellé restait suivi du vide.
    const ligne = (await screen.findByText(/Déposée par/)).closest('p');
    expect(ligne).toHaveTextContent('Omar Benfdila');
  });
});

describe('pages/invoices/InvoiceListPage — filtres et archivage', () => {
  it('ouvre sur les factures à traiter, archives exclues', () => {
    renderWithProviders(<InvoiceListPage />);

    expect(screen.getByText(/Facture #1/)).toBeInTheDocument();
    // L'archivée ne remonte que dans sa propre vue.
    expect(screen.queryByText(/Facture #2/)).not.toBeInTheDocument();
  });

  it('range les archives dans leur filtre, avec leur compte', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InvoiceListPage />);

    const onglet = screen.getByRole('tab', { name: /Archivées/ });
    expect(onglet).toHaveTextContent('1');

    await user.click(onglet);
    expect(await screen.findByText(/Facture #2/)).toBeInTheDocument();
  });

  it('archive une facture depuis son détail', async () => {
    const user = userEvent.setup();
    renderWithProviders(<InvoiceListPage />);

    await user.click(screen.getByText(/Facture #1/));
    await user.click(await screen.findByRole('button', { name: /Archiver/ }));

    await waitFor(() => expect(archiver).toHaveBeenCalledWith(1, expect.anything()));
  });
});
