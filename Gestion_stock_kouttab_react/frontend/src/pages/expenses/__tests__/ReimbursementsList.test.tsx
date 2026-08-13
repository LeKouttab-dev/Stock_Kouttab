import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { Reimbursement } from '@/types/api';

/**
 * L'écran des remboursements.
 *
 * Il n'existait pas. Le PDF et le tableur étaient produits à chaque versement,
 * joints au courriel de la comptabilité, et montrés à personne : le bénévole
 * voyait une pastille verte sur sa note et rien d'autre — ni date de versement,
 * ni montant, ni preuve à produire. L'API l'autorisait pourtant déjà à
 * télécharger le sien.
 */

const telecharger = vi.fn();

const VERSEMENT: Reimbursement = {
  id: 3,
  id_user: 7,
  date_remboursement: '2026-08-10',
  moyen: 'Virement bancaire',
  etablissement: 'Wise',
  approuve_par: 'DTC',
  montant_total: '57.40',
  a_pdf: true,
  a_xlsx: true,
  expenses: [
    { id: 1, date_depense: '2026-06-12', montant: '42.90', fournisseur: 'Carrefour' },
    { id: 2, date_depense: '2026-06-20', montant: '14.50', fournisseur: 'Metro' },
  ],
};

let versements: Reimbursement[] = [VERSEMENT];

vi.mock('@/api/endpoints/reimbursements', () => ({
  useReimbursements: () => ({ data: versements, isLoading: false }),
  reimbursementDocumentPath: (id: number, format: string) =>
    `/reimbursements/${id}/document?format=${format}`,
  reimbursementQueryKeys: { all: ['reimbursements'] },
}));
vi.mock('@/hooks/useDownloadAttachment', () => ({
  useDownloadAttachment: () => ({ download: telecharger, downloadingId: null }),
}));

import { ReimbursementsList } from '../ReimbursementsList';

describe('pages/expenses/ReimbursementsList', () => {
  it('annonce le versement : date et montant, sans avoir à déplier', () => {
    renderWithProviders(<ReimbursementsList />);

    expect(screen.getByText(/10\/08\/2026/)).toBeInTheDocument();
    expect(screen.getByText(/57,40/)).toBeInTheDocument();
  });

  it('donne le justificatif au bénévole', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReimbursementsList />);

    await user.click(screen.getByText(/10\/08\/2026/));
    await user.click(await screen.findByRole('button', { name: /Justificatif \(PDF\)/ }));

    expect(telecharger).toHaveBeenCalledWith(
      '/reimbursements/3/document?format=pdf',
      expect.stringContaining('.pdf'),
      3,
    );
  });

  it('détaille les notes que le versement a soldées', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReimbursementsList />);
    await user.click(screen.getByText(/10\/08\/2026/));

    expect(await screen.findByText(/Carrefour/)).toBeInTheDocument();
    expect(screen.getByText(/Metro/)).toBeInTheDocument();
    expect(screen.getByText(/Virement bancaire/)).toBeInTheDocument();
  });

  it('ne propose pas un document absent', async () => {
    const user = userEvent.setup();
    versements = [{ ...VERSEMENT, a_pdf: false }];
    renderWithProviders(<ReimbursementsList />);

    await user.click(screen.getByText(/10\/08\/2026/));

    // Promettre un téléchargement qui rendrait un 404 est pire que ne rien
    // proposer : c'est ce que faisait `a_pdf`, qui testait la présence du
    // chemin et non celle du fichier.
    expect(screen.queryByRole('button', { name: /Justificatif \(PDF\)/ })).not.toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Justificatif \(Excel\)/ })).toBeInTheDocument();

    versements = [VERSEMENT];
  });
});
