import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { Conversation } from '@/types/api';

/**
 * Espace de contact : des fils de discussion.
 *
 * Ce qui compte : la question ouvre un fil consultable, l'équipe voit sa boîte
 * et peut y changer le statut, et **aucun champ d'identité** n'est proposé — le
 * serveur reprend celle du compte connecté.
 */

const ouvrir = vi.fn();
const repondre = vi.fn();
const changerStatut = vi.fn();

let mesFils: Conversation[] = [];
let filsEquipe: Conversation[] = [];
let filOuvert: Conversation | undefined;
let gereDesFils = false;

const FIL: Conversation = {
  id: 1,
  id_user: 7,
  demandeur: 'Fatima Zahra',
  destinataire: 'compta',
  sujet: 'Ma note de frais de juin',
  statut: 'ouverte',
  attente_equipe: true,
  non_lu_demandeur: false,
  nombre_messages: 1,
  dernier_message: 'Elle est toujours en attente.',
  a_signaler: true,
  messages: [
    {
      id: 1,
      auteur_nom: 'Fatima Zahra',
      de_l_equipe: false,
      est_moi: true,
      corps: 'Elle est toujours en attente.',
    },
  ],
};

vi.mock('@/api/endpoints/contact', () => ({
  useMyConversations: () => ({ data: mesFils, isLoading: false }),
  useTeamConversations: () => ({ data: filsEquipe, isLoading: false }),
  useConversation: () => ({ data: filOuvert, isLoading: false }),
  useOpenConversation: () => ({ mutate: ouvrir, isPending: false }),
  useReplyToConversation: () => ({ mutate: repondre, isPending: false }),
  useSetConversationStatut: () => ({ mutate: changerStatut, isPending: false }),
  useTransferConversation: () => ({ mutate: vi.fn(), isPending: false }),
  conversationQueryKeys: { all: ['conversations'] },
}));
vi.mock('@/api/endpoints/notifications', () => ({
  usePendingSummary: () => ({ data: { conversations_a_traiter: 2, conversations_non_lues: 1 } }),
  notificationQueryKeys: { all: ['notifications'] },
}));
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ can: () => gereDesFils }),
}));

import { ContactPage } from '../ContactPage';

describe('pages/contact/ContactPage', () => {
  beforeEach(() => {
    ouvrir.mockClear();
    repondre.mockClear();
    changerStatut.mockClear();
    mesFils = [FIL];
    filsEquipe = [FIL];
    filOuvert = FIL;
    gereDesFils = false;
  });

  it('ouvre un fil plutôt que d’envoyer un message sans retour', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);

    await user.click(screen.getByRole('tab', { name: /Nouvelle question/ }));
    await user.type(screen.getByLabelText(/Objet/), 'Ma note de frais de juin');
    await user.type(
      screen.getByLabelText(/Votre message/),
      'Assalamu alaykum, ma note du 12 juin est toujours en attente.',
    );
    await user.click(screen.getByRole('button', { name: /Envoyer/ }));

    await waitFor(() => expect(ouvrir).toHaveBeenCalled());
    expect(ouvrir.mock.calls[0][0]).toMatchObject({
      destinataire: 'compta',
      sujet: 'Ma note de frais de juin',
    });
  });

  it('ne demande ni nom ni adresse à l’auteur', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);
    await user.click(screen.getByRole('tab', { name: /Nouvelle question/ }));

    expect(screen.queryByLabelText(/Votre nom/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/adresse e-?mail/i)).not.toBeInTheDocument();
  });

  it('liste mes conversations et ouvre le fil', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);

    await user.click(screen.getByText('Ma note de frais de juin'));

    // Le fil, et non plus un accusé d'envoi : les messages sont là.
    expect(await screen.findByText('Elle est toujours en attente.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Répondre/ })).toBeInTheDocument();
  });

  it('poste une réponse dans le fil', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />);
    await user.click(screen.getByText('Ma note de frais de juin'));

    await user.type(await screen.findByLabelText(/Votre réponse/), 'Merci !');
    await user.click(screen.getByRole('button', { name: /Répondre/ }));

    await waitFor(() => expect(repondre).toHaveBeenCalled());
    expect(repondre.mock.calls[0][0]).toMatchObject({ id: 1, corps: 'Merci !' });
  });

  it('cache la boîte de l’équipe à qui ne la traite pas', () => {
    renderWithProviders(<ContactPage />);
    expect(screen.queryByRole('tab', { name: /À traiter/ })).not.toBeInTheDocument();
  });

  it('donne à l’équipe sa boîte et le changement de statut', async () => {
    const user = userEvent.setup();
    gereDesFils = true;
    renderWithProviders(<ContactPage />);

    const onglet = screen.getByRole('tab', { name: /À traiter/ });
    // La pastille dit combien de fils attendent, sans avoir à y entrer.
    expect(onglet).toHaveTextContent('2');

    await user.click(onglet);
    await user.click(screen.getAllByText('Ma note de frais de juin')[0]);

    // Le sélecteur de statut n'existe que pour l'équipe.
    expect(await screen.findByText(/Statut/)).toBeInTheDocument();
  });
});
