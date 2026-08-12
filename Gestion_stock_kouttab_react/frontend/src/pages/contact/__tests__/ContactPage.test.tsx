import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';

/**
 * Espace de contact.
 *
 * Ce qui compte : le message part avec le bon destinataire, et **aucun champ
 * d'identité** n'est proposé — le serveur reprend celle du compte connecté. Un
 * « votre nom » se remplit de n'importe quoi.
 */

const envoyer = vi.fn();

vi.mock('@/api/endpoints/contact', () => ({
  useSendContact: () => ({ mutate: envoyer, isPending: false }),
}));

import { ContactPage } from '../ContactPage';

describe('pages/contact/ContactPage', () => {
  it('envoie le message au destinataire choisi', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);

    await user.type(screen.getByLabelText(/Objet/), 'Ma note de frais de juin');
    await user.type(
      screen.getByLabelText(/Votre message/),
      'Assalamu alaykum, ma note du 12 juin est toujours en attente.',
    );
    await user.click(screen.getByRole('button', { name: /Envoyer/ }));

    await waitFor(() => expect(envoyer).toHaveBeenCalled());
    expect(envoyer.mock.calls[0][0]).toMatchObject({
      destinataire: 'compta',
      sujet: 'Ma note de frais de juin',
    });
  });

  it('ne demande ni nom ni adresse à l’auteur', () => {
    renderWithProviders(<ContactPage />);

    expect(screen.queryByLabelText(/Votre nom/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/adresse e-?mail/i)).not.toBeInTheDocument();
  });

  it('refuse un message trop court plutôt que de le laisser partir', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);
    envoyer.mockClear();

    await user.type(screen.getByLabelText(/Objet/), 'Bonjour');
    await user.type(screen.getByLabelText(/Votre message/), 'court');
    await user.click(screen.getByRole('button', { name: /Envoyer/ }));

    // Le serveur le refuserait de toute façon : mieux vaut le dire ici que
    // laisser croire à un envoi réussi.
    await waitFor(() => expect(screen.getByText(/quelques mots/)).toBeInTheDocument());
    expect(envoyer).not.toHaveBeenCalled();
  });
});
