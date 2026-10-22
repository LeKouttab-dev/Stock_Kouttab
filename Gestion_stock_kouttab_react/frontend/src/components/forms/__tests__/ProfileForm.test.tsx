import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { User } from '@/types/api';
import { ibanValide } from '@/lib/iban';

/**
 * Le RIB dans le profil : IBAN et relevé partent ensemble chez le trésorier.
 *
 * Ce qui compte : rien ne part sans un IBAN valide ET un relevé, l'envoi est
 * indépendant de « Mettre à jour », et une fois transmis l'écran ne montre que
 * le constat (date, fin de l'IBAN) — il n'y a plus rien d'autre à montrer.
 */

const transmettre = vi.fn();
let profil: Partial<User> = {};

vi.mock('@/api/endpoints/auth', () => ({
  useProfile: () => ({ data: profil, isLoading: false }),
  useUpdateProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useTransmettreRib: () => ({ mutate: transmettre, isPending: false }),
}));

import { ProfileForm } from '../ProfileForm';

const BASE: Partial<User> = {
  nom: 'Benfdila',
  prenom: 'Omar',
  email: 'omar@exemple.test',
  telephone: '',
};

const IBAN = 'FR76 3000 1007 9412 3456 7890 185';

describe('components/forms/ProfileForm — RIB transmis au trésorier', () => {
  beforeEach(() => {
    transmettre.mockClear();
    profil = { ...BASE, rib_transmis_le: null };
  });

  it('envoie l’IBAN et le relevé ensemble', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileForm />);

    await user.type(screen.getByLabelText('IBAN'), IBAN);
    const fichier = new File(['%PDF-1.4'], 'rib.pdf', { type: 'application/pdf' });
    await user.upload(screen.getByTestId('rib-document-input'), fichier);
    await user.click(screen.getByRole('button', { name: /Envoyer au trésorier/ }));

    await waitFor(() => expect(transmettre).toHaveBeenCalled());
    expect(transmettre.mock.calls[0][0]).toEqual({ iban: IBAN, file: fichier });
  });

  it('refuse un IBAN faux sans rien envoyer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileForm />);

    await user.type(screen.getByLabelText('IBAN'), IBAN.slice(0, -1) + '6');
    await user.upload(
      screen.getByTestId('rib-document-input'),
      new File(['%PDF'], 'rib.pdf', { type: 'application/pdf' }),
    );
    await user.click(screen.getByRole('button', { name: /Envoyer au trésorier/ }));

    expect(screen.getByText(/IBAN invalide/)).toBeInTheDocument();
    expect(transmettre).not.toHaveBeenCalled();
  });

  it('exige le relevé', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileForm />);

    await user.type(screen.getByLabelText('IBAN'), IBAN);
    await user.click(screen.getByRole('button', { name: /Envoyer au trésorier/ }));

    expect(screen.getByText(/Joignez le relevé/)).toBeInTheDocument();
    expect(transmettre).not.toHaveBeenCalled();
  });

  it('une fois transmis, n’affiche que le constat', async () => {
    const user = userEvent.setup();
    profil = { ...BASE, rib_transmis_le: '2026-10-01T09:00:00', rib_iban_fin: '0185' };
    renderWithProviders(<ProfileForm />);

    expect(screen.getByText(/transmis au trésorier le 01\/10\/2026/)).toBeInTheDocument();
    expect(screen.getByText(/0185/)).toBeInTheDocument();
    expect(screen.queryByTestId('rib-document-input')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Transmettre un nouveau RIB/ }));
    expect(screen.getByTestId('rib-document-input')).toBeInTheDocument();
  });
});

describe('lib/iban — même contrôle que le serveur', () => {
  it.each([
    ['FR7630001007941234567890185', true],
    ['fr76 3000 1007 9412 3456 7890 185', true],
    ['FR7630001007941234567890186', false],
    ['GB82WEST12345698765432', true],
    ['FR76', false],
    ['', false],
  ])('%s → %s', (iban, attendu) => {
    expect(ibanValide(iban)).toBe(attendu);
  });
});
