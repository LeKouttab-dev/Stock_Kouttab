import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { EtatEnvois } from '@/types/api';

/**
 * L'écran restait vert pendant que rien ne partait.
 *
 * O2Switch a cessé de servir un certificat couvrant `mail.lekouttab.fr` et
 * présente celui du cluster : la poignée de main TLS échouait, et plus un seul
 * courriel n'est parti pendant des semaines. La file des envois comptables ne
 * le montrait pas — les notifications de dépôt n'y laissent aucune ligne — et
 * il a fallu qu'un utilisateur remarque le silence pour que la panne existe.
 *
 * La bannière d'état est ce qui manquait.
 */

let etat: EtatEnvois;

vi.mock('@/api/endpoints/admin', () => ({
  useEtatEnvois: () => ({ data: etat }),
  useOutboundEmails: () => ({ data: [], isLoading: false, refetch: vi.fn() }),
  useRetryOutboundEmail: () => ({ mutate: vi.fn(), isPending: false }),
}));

const SAIN: EtatEnvois = {
  email_enabled: true,
  smtp_configure: true,
  smtp_joignable: true,
  smtp_erreur: null,
  destinataires_compta: ['comptabilite@example.test'],
  en_attente: 0,
  en_echec: 0,
};

async function afficher(etatCourant: EtatEnvois) {
  etat = etatCourant;
  const { OutboundEmailsSection } = await import('../OutboundEmailsSection');
  renderWithProviders(<OutboundEmailsSection />);
}

describe('pages/admin/OutboundEmailsSection', () => {
  it('reste discret quand le serveur répond', async () => {
    await afficher(SAIN);
    expect(screen.getByText(/le serveur d’envoi répond/i)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('alerte, et donne le motif, quand le SMTP ne répond plus', async () => {
    await afficher({
      ...SAIN,
      smtp_joignable: false,
      smtp_erreur: 'Le certificat presente par mail.lekouttab.fr ne couvre pas ce nom d’hote.',
    });

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/aucun courriel ne peut partir/i)).toBeInTheDocument();
    // Le motif, pas seulement le symptôme : sans lui, on cherche du côté du
    // mot de passe alors que c'est le nom d'hôte qui est en cause.
    expect(screen.getByText(/certificat/i)).toBeInTheDocument();
  });

  it('signale un coupe-circuit baissé, que la file affiche ou non des échecs', async () => {
    await afficher({ ...SAIN, email_enabled: false, smtp_joignable: false });
    expect(screen.getByText(/EMAIL_ENABLED=false/)).toBeInTheDocument();
  });

  it('signale l’absence de destinataire comptable', async () => {
    await afficher({ ...SAIN, destinataires_compta: [] });
    expect(screen.getByText(/COMPTA_EMAIL/)).toBeInTheDocument();
  });
});
