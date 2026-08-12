import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { User } from '@/types/api';

/**
 * Dépôt du RIB en document, dans le profil.
 *
 * L'IBAN saisi sert au virement, ce document sert de preuve. Le point à ne pas
 * casser : le dépôt est **indépendant** de la soumission du profil — sans quoi
 * corriger un numéro de téléphone obligerait à re-téléverser son RIB.
 */

const televerser = vi.fn();
const supprimer = vi.fn();
let profil: Partial<User> = {};

vi.mock('@/api/endpoints/auth', () => ({
  useProfile: () => ({ data: profil, isLoading: false }),
  useUpdateProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useUploadRibDocument: () => ({ mutate: televerser, isPending: false }),
  useDeleteRibDocument: () => ({ mutate: supprimer, isPending: false }),
}));

import { ProfileForm } from '../ProfileForm';

const BASE: Partial<User> = {
  nom: 'Benfdila',
  prenom: 'Omar',
  email: 'omar@exemple.test',
  telephone: '',
  rib: '',
};

describe('components/forms/ProfileForm — RIB en document', () => {
  beforeEach(() => {
    televerser.mockClear();
    supprimer.mockClear();
    profil = { ...BASE, rib_document_nom: null };
  });

  it('téléverse le document sans passer par « Mettre à jour »', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileForm />);

    expect(screen.getByText(/Aucun document déposé/)).toBeInTheDocument();

    const fichier = new File(['%PDF-1.4'], 'rib.pdf', { type: 'application/pdf' });
    await user.upload(screen.getByTestId('rib-document-input'), fichier);

    await waitFor(() => expect(televerser).toHaveBeenCalled());
    expect(televerser.mock.calls[0][0]).toBe(fichier);
  });

  it('affiche le document déposé et permet de le retirer', async () => {
    const user = userEvent.setup();
    profil = { ...BASE, rib_document_nom: 'rib-banque.pdf' };
    renderWithProviders(<ProfileForm />);

    expect(screen.getByText('rib-banque.pdf')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Supprimer/ }));

    await waitFor(() => expect(supprimer).toHaveBeenCalled());
  });
});
