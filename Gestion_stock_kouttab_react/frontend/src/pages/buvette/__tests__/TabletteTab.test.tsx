import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
import type { CaisseEtat } from '@/types/api';
import { TabletteTab } from '../tabs/TabletteTab';
import { BASE_URL, connecter } from './helpers';

const ETAT: CaisseEtat = {
  batterie_pct: 82,
  en_charge: true,
  version_code: 7,
  version_name: '0.7.0',
  sumup_connecte: true,
  lecteur_connecte: true,
  lecteur_batterie_pct: 64,
  ventes_en_attente: 0,
  ventes_rejetees: 1,
  ecran: 'accueil',
  recu_at: '2026-10-09T18:00:00',
  secondes_depuis: 40,
};

function etat(e: CaisseEtat | null) {
  server.use(http.get(`${BASE_URL}/buvette/caisse/etat`, () => HttpResponse.json({ etat: e })));
}

describe('pages/buvette/tabs/TabletteTab : état', () => {
  it('affiche un contact récent en vert, avec les détails', async () => {
    etat(ETAT);
    renderWithProviders(<TabletteTab />);

    const contact = await screen.findByTestId('dernier-contact');
    expect(contact).toHaveTextContent('il y a 40 s');
    expect(contact).toHaveAttribute('data-silencieuse', 'false');
    expect(screen.getByText('82 %')).toBeInTheDocument();
    expect(screen.getByText('(en charge)')).toBeInTheDocument();
    expect(screen.getByText(/0\.7\.0/)).toBeInTheDocument();
    expect(screen.getByText('64 %')).toBeInTheDocument();
    expect(screen.getByText('Accueil')).toBeInTheDocument();
  });

  it('passe en rouge au-delà de 5 minutes sans nouvelles', async () => {
    etat({ ...ETAT, secondes_depuis: 600 });
    renderWithProviders(<TabletteTab />);

    const contact = await screen.findByTestId('dernier-contact');
    expect(contact).toHaveTextContent('il y a 10 min');
    expect(contact).toHaveAttribute('data-silencieuse', 'true');
    expect(contact).toHaveClass('text-red-700');
  });

  it('dit « jamais vue » quand la tablette ne s’est jamais annoncée', async () => {
    etat(null);
    renderWithProviders(<TabletteTab />);

    expect(await screen.findByTestId('dernier-contact')).toHaveTextContent('jamais vue');
  });
});

describe('pages/buvette/tabs/TabletteTab : destinataires', () => {
  it('ajoute une adresse, refuse une adresse invalide, et enregistre', async () => {
    const comptes = [{ id: 4, email: 'stock@lekouttab.fr', nom: 'Bilal' }];
    let corps: { recap_destinataires: string[] } | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/reglages`, () =>
        HttpResponse.json({
          recap_destinataires: ['tresorier@lekouttab.fr'],
          comptes_admin_stock: comptes,
        }),
      ),
      http.put(`${BASE_URL}/buvette/reglages`, async ({ request }) => {
        corps = (await request.json()) as { recap_destinataires: string[] };
        return HttpResponse.json({ ...corps, comptes_admin_stock: comptes });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    expect(await screen.findByText('tresorier@lekouttab.fr')).toBeInTheDocument();
    expect(screen.getByText('Bilal')).toBeInTheDocument();

    const champ = screen.getByLabelText('adresse@exemple.fr');
    await user.type(champ, 'pas-une-adresse');
    await user.click(screen.getByRole('button', { name: /Ajouter/ }));
    expect(screen.getByText('Adresse e-mail invalide.')).toBeInTheDocument();

    await user.clear(champ);
    await user.type(champ, 'omar@lekouttab.fr{Enter}');
    expect(screen.getByText('omar@lekouttab.fr')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }));
    await waitFor(() =>
      expect(corps).toEqual({
        recap_destinataires: ['tresorier@lekouttab.fr', 'omar@lekouttab.fr'],
      }),
    );
  });

  it('cache les réglages à la comptabilité', async () => {
    etat(ETAT);
    renderWithProviders(<TabletteTab />);
    connecter('Compta');

    await screen.findByTestId('dernier-contact');
    expect(screen.queryByText('Destinataires des e-mails de la buvette')).not.toBeInTheDocument();
  });
});
