import { afterEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, within } from '@/test/test-utils';
import { grouperProduits } from '@/lib/buvette';
import type { BuvetteProduct } from '@/types/api';
import { BuvettePage } from '../BuvettePage';
import { BASE_URL, connecter } from './helpers';

function produit(
  id: number,
  name: string,
  caisse_category: BuvetteProduct['caisse_category'],
  barcode: string | null = null,
): BuvetteProduct {
  return {
    id,
    helloasso_tier_id: null,
    name,
    description: null,
    price_cents: 150,
    quantity: 10,
    seuil_alerte: 2,
    emoji: '🍪',
    image_url: null,
    is_active: true,
    alert_sent: false,
    last_synced_at: null,
    low_stock: false,
    caisse_category,
    barcode,
    dernier_prix_achat_cents: null,
  };
}

const PRODUITS = [
  produit(1, 'Coca', 'boissons', '5449000000996'),
  produit(2, 'Thé glacé', 'boissons'),
  produit(3, 'Cookie', 'sucre_sale'),
  produit(4, 'Café allongé', 'cafe'),
  produit(5, 'Pâtes', 'epicerie', '3038350012005'),
  produit(6, 'Vieux produit HelloAsso', null),
];

function rendre() {
  server.use(http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json(PRODUITS)));
  renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette'] });
  connecter('AdminStock');
}

function titresDesGroupes(): string[] {
  return screen
    .getAllByRole('button', { expanded: true })
    .concat(screen.queryAllByRole('button', { expanded: false }))
    .map((b) => b.textContent ?? '')
    .filter((t) => /\(\d+\)$/.test(t) && !t.startsWith('Sans code'));
}

afterEach(() => {
  window.localStorage.clear();
});

describe('lib/buvette : grouperProduits', () => {
  it("range dans l'ordre de la tablette, puis hors tablette, sans groupe vide", () => {
    const groupes = grouperProduits([
      { id: 1, caisse_category: 'epicerie' },
      { id: 2, caisse_category: null },
      { id: 3, caisse_category: 'sucre_sale' },
      { id: 4, caisse_category: 'inconnu' },
    ]);
    expect(groupes.map((g) => g.groupe)).toEqual(['sucre_sale', 'epicerie', 'aucun']);
    expect(groupes[2].produits.map((p) => p.id)).toEqual([2, 4]);
  });
});

describe('pages/buvette/BuvettePage : produits groupés', () => {
  it('affiche les sections dans l’ordre avec leurs compteurs', async () => {
    rendre();
    await screen.findByText('Coca');
    expect(titresDesGroupes()).toEqual([
      'Sucré-salé (1)',
      'Boissons (2)',
      'Café (1)',
      'Épicerie (1)',
      'Hors tablette (1)',
    ]);
    const boissons = screen.getByTestId('groupe-boissons');
    expect(within(boissons).getByText('Coca')).toBeInTheDocument();
    expect(within(boissons).getByText('Thé glacé')).toBeInTheDocument();
  });

  it('replie une section et s’en souvient', async () => {
    const user = userEvent.setup();
    rendre();
    await screen.findByText('Coca');

    const entete = screen.getByRole('button', { name: 'Boissons (2)' });
    await user.click(entete);
    expect(entete).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Coca')).not.toBeInTheDocument();
    expect(screen.getByText('Cookie')).toBeInTheDocument();
    expect(
      JSON.parse(window.localStorage.getItem('buvette.produits.groupesReplies') ?? '[]'),
    ).toEqual(['boissons']);
  });

  it('ignore un stockage illisible : tout reste ouvert', async () => {
    window.localStorage.setItem('buvette.produits.groupesReplies', 'pas du json');
    rendre();
    expect(await screen.findByText('Café allongé')).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { expanded: false })).toHaveLength(0);
  });

  it('relit l’état mémorisé', async () => {
    window.localStorage.setItem('buvette.produits.groupesReplies', JSON.stringify(['cafe']));
    rendre();
    await screen.findByText('Coca');
    expect(screen.getByRole('button', { name: 'Café (1)' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.queryByText('Café allongé')).not.toBeInTheDocument();
  });

  it('cherche à travers les groupes, ouvre ceux qui restent et masque les vides', async () => {
    window.localStorage.setItem('buvette.produits.groupesReplies', JSON.stringify(['boissons']));
    const user = userEvent.setup();
    rendre();
    await screen.findByText('Cookie');

    await user.type(screen.getByLabelText(/Rechercher un produit/), 'the glace');
    expect(screen.getByText('Thé glacé')).toBeInTheDocument();
    expect(titresDesGroupes()).toEqual(['Boissons (1)']);

    await user.clear(screen.getByLabelText(/Rechercher un produit/));
    await user.type(screen.getByLabelText(/Rechercher un produit/), 'introuvable');
    expect(screen.getByText('Aucun produit ne correspond à cette recherche.')).toBeInTheDocument();
  });

  it('le filtre « Sans code-barres » s’applique dans chaque groupe', async () => {
    const user = userEvent.setup();
    rendre();
    await screen.findByText('Coca');

    await user.click(screen.getByRole('button', { name: /Sans code-barres/ }));
    expect(titresDesGroupes()).toEqual([
      'Sucré-salé (1)',
      'Boissons (1)',
      'Café (1)',
      'Hors tablette (1)',
    ]);
    expect(screen.queryByText('Coca')).not.toBeInTheDocument();
    expect(screen.getByText('Thé glacé')).toBeInTheDocument();
  });
});
