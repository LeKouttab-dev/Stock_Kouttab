import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, waitFor, within } from '@/test/test-utils';
import { Toaster } from '@/components/ui/toast';
import type { BuvetteProduct } from '@/types/api';
import { BuvettePage } from '../BuvettePage';
import { BASE_URL, connecter } from './helpers';

const CAFE: BuvetteProduct = {
  id: 7,
  helloasso_tier_id: null,
  name: 'Café',
  description: null,
  price_cents: 150,
  quantity: 12,
  seuil_alerte: 5,
  emoji: '☕',
  image_url: null,
  is_active: true,
  alert_sent: false,
  last_synced_at: null,
  low_stock: false,
  caisse_category: 'cafe',
  dernier_prix_achat_cents: 45,
};

function servirProduits(produit: BuvetteProduct = CAFE) {
  server.use(http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json([produit])));
}

function rendre() {
  renderWithProviders(
    <>
      <BuvettePage />
      <Toaster />
    </>,
    { routerEntries: ['/buvette'] },
  );
}

async function ouvrirReappro() {
  const user = userEvent.setup();
  rendre();
  connecter('AdminStock');
  await user.click(await screen.findByRole('button', { name: 'Réapprovisionner' }));
  const fenetre = await screen.findByRole('dialog');
  return { user, fenetre };
}

describe('pages/buvette/BuvettePage : carte produit', () => {
  it('propose « Modifier » et « Réapprovisionner », sans raccourcis sur la carte', async () => {
    servirProduits();
    rendre();
    connecter('AdminStock');

    expect(await screen.findByRole('button', { name: 'Réapprovisionner' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Modifier' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ajuster' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Ajouter \d+/ })).not.toBeInTheDocument();
  });

  it('ne propose ni modification ni réappro à la comptabilité (lecture seule)', async () => {
    servirProduits();
    renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette'] });
    connecter('Compta');

    expect(await screen.findByText('Café')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Réapprovisionner' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument();
  });

  it('« Modifier » ouvre la fiche sans champ quantité et n’envoie pas de stock', async () => {
    servirProduits();
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE_URL}/buvette/products/7`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...CAFE, name: 'Café serré' });
      }),
    );
    const user = userEvent.setup();
    rendre();
    connecter('AdminStock');

    await user.click(await screen.findByRole('button', { name: 'Modifier' }));
    const fenetre = await screen.findByRole('dialog');
    expect(within(fenetre).getByText('Modifier le produit')).toBeInTheDocument();
    expect(within(fenetre).queryByLabelText(/^Quantité/)).not.toBeInTheDocument();

    const nom = within(fenetre).getByLabelText(/Nom du produit/);
    await user.clear(nom);
    await user.type(nom, 'Café serré');
    await user.click(within(fenetre).getByRole('button', { name: /Mettre à jour|Enregistrer/ }));

    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps!.name).toBe('Café serré');
    expect(corps).not.toHaveProperty('quantity');
  });
});

describe('pages/buvette/BuvettePage : réapprovisionnement', () => {
  it('cumule saisie et raccourcis, affiche le stock après et envoie le POST', async () => {
    servirProduits();
    let corps: unknown = null;
    server.use(
      http.post(`${BASE_URL}/buvette/products/7/reappro`, async ({ request }) => {
        corps = await request.json();
        return HttpResponse.json({
          produit: { ...CAFE, quantity: 42 },
          reappro: {
            id: 1,
            product_id: 7,
            nom: 'Café',
            quantite: 30,
            prix_achat_unitaire_cents: 45,
            total_cents: 1350,
            origine: 'app',
            commentaire: 'Livraison Metro',
            fait_par: 'Omar',
            stock_avant: 12,
            stock_apres: 42,
            created_at: '2026-10-09T10:00:00Z',
          },
        });
      }),
    );
    const { user, fenetre } = await ouvrirReappro();

    expect(within(fenetre).getByTestId('reappro-stock-actuel')).toHaveTextContent('12');
    // Prix pré-rempli avec le dernier prix d'achat.
    expect(within(fenetre).getByLabelText(/Prix d’achat unitaire/)).toHaveValue('0,45');

    // Saisie, puis raccourcis qui s'y ajoutent.
    await user.type(within(fenetre).getByLabelText(/Quantité apportée/), '15');
    await user.click(within(fenetre).getByRole('button', { name: 'Ajouter 10' }));
    await user.click(within(fenetre).getByRole('button', { name: 'Ajouter 5' }));
    expect(within(fenetre).getByLabelText(/Quantité apportée/)).toHaveValue('30');
    expect(within(fenetre).getByTestId('reappro-stock-apres')).toHaveTextContent(
      'Stock après : 12 + 30 = 42',
    );
    expect(within(fenetre).getByTestId('reappro-total')).toHaveTextContent('13.50 €');

    await user.type(within(fenetre).getByLabelText(/Commentaire/), 'Livraison Metro');
    await user.click(within(fenetre).getByRole('button', { name: 'Valider' }));

    await waitFor(() =>
      expect(corps).toEqual({
        quantite: 30,
        prix_achat_unitaire_cents: 45,
        commentaire: 'Livraison Metro',
      }),
    );
    expect(await screen.findByText('Nouveau stock : 42')).toBeInTheDocument();
  });

  it('remet la quantité à zéro', async () => {
    servirProduits();
    const { user, fenetre } = await ouvrirReappro();

    await user.click(within(fenetre).getByRole('button', { name: 'Ajouter 20' }));
    await user.click(within(fenetre).getByRole('button', { name: 'Ajouter 30' }));
    expect(within(fenetre).getByLabelText(/Quantité apportée/)).toHaveValue('50');

    await user.click(within(fenetre).getByRole('button', { name: 'Remettre à zéro' }));
    expect(within(fenetre).getByLabelText(/Quantité apportée/)).toHaveValue('');
    expect(within(fenetre).getByTestId('reappro-stock-apres')).toHaveTextContent(
      'Stock après : 12 + 0 = 12',
    );
  });

  it('exige un prix d’achat et une quantité avant d’envoyer', async () => {
    servirProduits({ ...CAFE, dernier_prix_achat_cents: null });
    let appels = 0;
    server.use(
      http.post(`${BASE_URL}/buvette/products/7/reappro`, () => {
        appels += 1;
        return HttpResponse.json({});
      }),
    );
    const { user, fenetre } = await ouvrirReappro();

    expect(within(fenetre).getByLabelText(/Prix d’achat unitaire/)).toHaveValue('');
    await user.click(within(fenetre).getByRole('button', { name: 'Valider' }));
    expect(
      within(fenetre).getByText('Saisissez une quantité entre 1 et 10 000.'),
    ).toBeInTheDocument();
    expect(
      within(fenetre).getByText('Saisissez le prix d’achat unitaire, par exemple 0,45.'),
    ).toBeInTheDocument();

    await user.click(within(fenetre).getByRole('button', { name: 'Ajouter 5' }));
    await user.click(within(fenetre).getByRole('button', { name: 'Valider' }));
    expect(
      within(fenetre).getByText('Saisissez le prix d’achat unitaire, par exemple 0,45.'),
    ).toBeInTheDocument();
    expect(appels).toBe(0);
  });
});

describe('pages/buvette/BuvettePage : onglets', () => {
  it("ouvre l'onglet indiqué dans l'adresse", async () => {
    renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette?onglet=paiements'] });
    connecter('Super Admin');

    expect(await screen.findByText('Total encaissé (brut)')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Paiements/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('place l’onglet Réappros juste après Produits', async () => {
    renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette?onglet=reappros'] });
    connecter('Super Admin');

    const onglets = await screen.findAllByRole('tab');
    expect(onglets[0]).toHaveTextContent('Produits');
    expect(onglets[1]).toHaveTextContent('Réappros');
    expect(onglets[1]).toHaveAttribute('aria-selected', 'true');
    expect(
      await screen.findByText('Aucun réapprovisionnement sur cette période.'),
    ).toBeInTheDocument();
  });
});
