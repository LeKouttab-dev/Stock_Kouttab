import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, waitFor, within } from '@/test/test-utils';
import { appliquerOrdrePropose, deplacer, longueurEtiquette, produitsDuMenu } from '@/lib/buvette';
import type { BuvetteProduct } from '@/types/api';
import { TabletteTab } from '../tabs/TabletteTab';
import { BASE_URL, connecter } from './helpers';

function produit(id: number, name: string, extra: Partial<BuvetteProduct> = {}): BuvetteProduct {
  return {
    id,
    helloasso_tier_id: null,
    name,
    description: null,
    price_cents: 150,
    quantity: 10,
    seuil_alerte: 2,
    emoji: '🥤',
    image_url: null,
    is_active: true,
    alert_sent: false,
    last_synced_at: null,
    low_stock: false,
    caisse_category: 'sucre_sale',
    ordre_caisse: null,
    etiquette_type: null,
    etiquette_texte: null,
    ...extra,
  };
}

// Kinder rangé 1er, Twix 2e ; Bounty et Mars pas encore rangés (par nom, en fin).
const PRODUITS = [
  produit(1, 'Mars'),
  produit(2, 'Twix', { ordre_caisse: 2 }),
  produit(3, 'Kinder', { ordre_caisse: 1 }),
  produit(4, 'Bounty'),
  produit(5, 'Masqué', { is_active: false }),
  produit(6, 'Coca', { caisse_category: 'boissons' }),
];

function catalogue(produits: BuvetteProduct[] = PRODUITS) {
  server.use(http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json(produits)));
}

/** Ventes par produit (id → quantité) pour la période demandée. */
function ventes(parJours: Record<number, Record<number, number>>, appels?: number[]) {
  server.use(
    http.get(`${BASE_URL}/buvette/caisse/ordre-par-ventes`, ({ request }) => {
      const url = new URL(request.url);
      const jours = Number(url.searchParams.get('jours'));
      appels?.push(jours);
      const q = parJours[jours] ?? {};
      const produits = Object.entries(q)
        .sort((a, b) => b[1] - a[1])
        .map(([id, n]) => ({
          product_id: Number(id),
          name: '',
          ordre_caisse: null,
          quantite_vendue: n,
        }));
      return HttpResponse.json({
        categorie: url.searchParams.get('categorie'),
        jours,
        debut: '2026-09-11',
        fin: '2026-10-10',
        produits,
      });
    }),
  );
}

function capturerOrdre() {
  const envois: { categorie: string; product_ids: number[] }[] = [];
  server.use(
    http.put(`${BASE_URL}/buvette/caisse/ordre`, async ({ request }) => {
      const corps = (await request.json()) as { categorie: string; product_ids: number[] };
      envois.push(corps);
      return HttpResponse.json({ categorie: corps.categorie, produits: [] });
    }),
  );
  return envois;
}

function nomsAffiches(): string[] {
  return screen
    .getAllByTestId('ligne-menu')
    .map(
      (li) => within(li).getByText(/^[A-ZÀ-Ü]/, { selector: 'p.font-medium' }).textContent ?? '',
    );
}

describe('lib/buvette : menu de la tablette', () => {
  it('ordonne un onglet : rangés, puis non rangés par nom ; actifs seulement', () => {
    expect(produitsDuMenu(PRODUITS, 'sucre_sale').map((p) => p.name)).toEqual([
      'Kinder',
      'Twix',
      'Bounty',
      'Mars',
    ]);
  });

  it('déplace un élément et applique un ordre proposé', () => {
    expect(deplacer([1, 2, 3, 4], 0, 2)).toEqual([2, 3, 1, 4]);
    expect(deplacer([1, 2, 3], 2, 5)).toEqual([1, 2, 3]);
    // Un produit inconnu de la proposition garde sa place relative, en fin.
    expect(appliquerOrdrePropose([1, 2, 3, 4], [3, 1, 99])).toEqual([3, 1, 2, 4]);
  });

  it('compte les caractères comme le serveur (emoji = 1)', () => {
    expect(longueurEtiquette('  Fait   maison ')).toBe(11);
    expect(longueurEtiquette('🍰🍰')).toBe(2);
  });
});

describe('pages/buvette/tabs/MenuTablette', () => {
  it('liste les produits de l’onglet dans l’ordre de la tablette, avec leurs ventes', async () => {
    catalogue();
    ventes({ 30: { 1: 7, 3: 1 } });
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    expect(await screen.findByText('Menu de la tablette')).toBeInTheDocument();
    await waitFor(() => expect(nomsAffiches()).toEqual(['Kinder', 'Twix', 'Bounty', 'Mars']));
    expect(screen.queryByText('Masqué')).not.toBeInTheDocument();
    expect(screen.queryByText('Coca')).not.toBeInTheDocument();
    const mars = screen.getAllByTestId('ligne-menu')[3];
    await waitFor(() => expect(within(mars).getByText('7 vendus (30 j)')).toBeInTheDocument());
  });

  it('réordonne avec les flèches et enregistre l’ordre complet de l’onglet', async () => {
    catalogue();
    ventes({});
    const envois = capturerOrdre();
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    await screen.findByRole('button', { name: 'Descendre Kinder' });
    expect(screen.getByRole('button', { name: 'Monter Kinder' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Descendre Mars' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Descendre Kinder' }));
    await waitFor(() => expect(envois).toHaveLength(1));
    expect(envois[0]).toEqual({ categorie: 'sucre_sale', product_ids: [2, 3, 4, 1] });
    expect(nomsAffiches()).toEqual(['Twix', 'Kinder', 'Bounty', 'Mars']);
  });

  it('change d’onglet', async () => {
    catalogue();
    ventes({});
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    await user.click(await screen.findByRole('tab', { name: 'Boissons' }));
    await waitFor(() => expect(nomsAffiches()).toEqual(['Coca']));
    await user.click(screen.getByRole('tab', { name: 'Café' }));
    expect(
      await screen.findByText('Aucun produit affiché dans cet onglet de la tablette.'),
    ).toBeInTheDocument();
  });

  it('« Trier par ventes » : période choisie, confirmation, puis ordre enregistré', async () => {
    catalogue();
    const appels: number[] = [];
    ventes({ 30: {}, 90: { 1: 12, 4: 5, 2: 1 } }, appels);
    const envois = capturerOrdre();
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    await user.selectOptions(await screen.findByLabelText('Période des ventes'), '90');
    await user.click(screen.getByRole('button', { name: 'Trier par ventes' }));
    const dialogue = await screen.findByRole('dialog');
    expect(dialogue).toHaveTextContent('Sucré-salé');
    expect(dialogue).toHaveTextContent('3 mois');
    expect(envois).toHaveLength(0);

    await user.click(within(dialogue).getByRole('button', { name: 'Trier' }));
    await waitFor(() => expect(envois).toHaveLength(1));
    expect(appels).toContain(90);
    // Mars (12), Bounty (5), Twix (1), puis Kinder, absent de la proposition.
    expect(envois[0]).toEqual({ categorie: 'sucre_sale', product_ids: [1, 4, 2, 3] });
  });

  it('pose une étiquette fixe et affiche son aperçu', async () => {
    catalogue();
    ventes({});
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE_URL}/buvette/products/:id`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...PRODUITS[2], ...corps });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    await user.selectOptions(await screen.findByLabelText('Étiquette de Kinder'), 'nouveaute');
    await waitFor(() => expect(corps).toEqual({ etiquette_type: 'nouveaute' }));
    const pastille = screen.getByTestId('pastille-etiquette');
    expect(pastille).toHaveTextContent('Nouveauté');
    expect(pastille).toHaveClass('bg-green-600');
  });

  it('étiquette libre : bornée à 20 caractères, vide refusée, envoyée nettoyée', async () => {
    catalogue();
    ventes({});
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE_URL}/buvette/products/:id`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...PRODUITS[2], ...corps });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    await user.selectOptions(await screen.findByLabelText('Étiquette de Kinder'), 'libre');
    // Choisir « Texte libre… » n'envoie rien tant que le texte n'est pas validé.
    expect(corps).toBeNull();
    const champ = screen.getByLabelText('Texte de l’étiquette de Kinder');

    await user.type(champ, '   ');
    await user.click(screen.getByRole('button', { name: 'Valider' }));
    expect(screen.getByText('Saisissez le texte de l’étiquette.')).toBeInTheDocument();
    expect(corps).toBeNull();

    await user.clear(champ);
    await user.type(champ, 'Recette de la maison du Kouttâb');
    expect(champ).toHaveValue('Recette de la maison');
    expect(screen.getByText('20/20')).toBeInTheDocument();
    expect(screen.getByTestId('pastille-etiquette')).toHaveAttribute('data-type', 'libre');

    await user.click(screen.getByRole('button', { name: 'Valider' }));
    await waitFor(() =>
      expect(corps).toEqual({ etiquette_type: 'libre', etiquette_texte: 'Recette de la maison' }),
    );
  });

  it('retire l’étiquette (« Aucune étiquette » envoie null)', async () => {
    catalogue([produit(3, 'Kinder', { etiquette_type: 'promo' })]);
    ventes({});
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE_URL}/buvette/products/:id`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...PRODUITS[2], ...corps });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TabletteTab />);
    connecter('AdminBenevoles');

    const choix = await screen.findByLabelText('Étiquette de Kinder');
    await waitFor(() => expect(choix).toHaveValue('promo'));
    await user.selectOptions(choix, '');
    await waitFor(() => expect(corps).toEqual({ etiquette_type: null }));
  });

  it('n’apparaît pas pour la comptabilité', async () => {
    catalogue();
    renderWithProviders(<TabletteTab />);
    connecter('Compta');

    await screen.findByTestId('dernier-contact');
    expect(screen.queryByText('Menu de la tablette')).not.toBeInTheDocument();
  });
});
