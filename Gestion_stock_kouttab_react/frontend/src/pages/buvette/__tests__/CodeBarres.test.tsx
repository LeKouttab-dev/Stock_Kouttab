import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import {
  fireEvent,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from '@/test/test-utils';
import { Toaster } from '@/components/ui/toast';
import type { BarcodeLookupResponse, BuvetteProduct } from '@/types/api';
import { BuvettePage } from '../BuvettePage';
import { BASE_URL, connecter } from './helpers';

// La caméra n'existe pas en test : le lecteur est remplacé par un bouton qui
// « lit » toujours le même code.
vi.mock('@/components/scanner/BarcodeScanner', () => ({
  BarcodeScanner: ({ open, onDetected }: { open: boolean; onDetected: (code: string) => void }) =>
    open ? (
      <button type="button" onClick={() => onDetected('3017620422003')}>
        Simuler le scan
      </button>
    ) : null,
}));

const CODE = '3017620422003';
const PHOTO_HELLOASSO = 'https://cdn.helloasso.com/img/kinder-bueno.jpg';

const KINDER: BuvetteProduct = {
  id: 11,
  helloasso_tier_id: 4242,
  name: 'KINDER - BUENO',
  description: null,
  price_cents: 150,
  quantity: 10,
  seuil_alerte: 5,
  emoji: '🍫',
  image_url: PHOTO_HELLOASSO,
  is_active: true,
  alert_sent: false,
  last_synced_at: null,
  low_stock: false,
  caisse_category: 'sucre_sale',
  barcode: null,
  dernier_prix_achat_cents: 80,
};

const SODA: BuvetteProduct = {
  ...KINDER,
  id: 12,
  helloasso_tier_id: null,
  name: 'Canette de soda',
  emoji: '🥤',
  image_url: null,
  caisse_category: 'boissons',
  barcode: '8000500310427',
};

const MARS: BuvetteProduct = {
  ...KINDER,
  id: 13,
  helloasso_tier_id: 4243,
  name: 'Mars',
  image_url: null,
  barcode: null,
};

function servirProduits(produits: BuvetteProduct[] = [KINDER, SODA, MARS]) {
  server.use(http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json(produits)));
}

function servirLookup(reponse: Partial<BarcodeLookupResponse> = {}) {
  server.use(
    http.get(`${BASE_URL}/stock/lookup-barcode/:code`, ({ params }) =>
      HttpResponse.json({
        barcode: String(params.code),
        found_in: null,
        stock_item: null,
        buvette_product: null,
        openfoodfacts: null,
        ...reponse,
      }),
    ),
  );
}

/** Capture le corps du PATCH envoyé pour le produit `id`. */
function capturerPatch(id: number, renvoi: (corps: Record<string, unknown>) => BuvetteProduct) {
  const appels: Record<string, unknown>[] = [];
  server.use(
    http.patch(`${BASE_URL}/buvette/products/${id}`, async ({ request }) => {
      const corps = (await request.json()) as Record<string, unknown>;
      appels.push(corps);
      return HttpResponse.json(renvoi(corps));
    }),
  );
  return appels;
}

function rendre() {
  renderWithProviders(
    <>
      <BuvettePage />
      <Toaster />
    </>,
    { routerEntries: ['/buvette'] },
  );
  connecter('AdminStock');
}

async function scannerDepuisLaPage() {
  const user = userEvent.setup();
  rendre();
  await screen.findByText('KINDER - BUENO');
  await user.click(screen.getByRole('button', { name: 'Scanner' }));
  await user.click(await screen.findByRole('button', { name: 'Simuler le scan' }));
  return user;
}

describe('pages/buvette : scan d’un code inconnu', () => {
  it('associe le code à un produit existant sans rien écraser, puis ouvre le réappro', async () => {
    servirProduits();
    servirLookup();
    const appels = capturerPatch(11, (corps) => ({ ...KINDER, ...corps }));
    const user = await scannerDepuisLaPage();

    const fenetre = await screen.findByRole('dialog');
    expect(within(fenetre).getByText('Code-barres inconnu')).toBeInTheDocument();
    expect(within(fenetre).getByText(CODE)).toBeInTheDocument();
    // Seuls les produits sans code-barres sont proposés.
    expect(
      within(fenetre).getByRole('button', { name: 'Associer à KINDER - BUENO' }),
    ).toBeInTheDocument();
    expect(within(fenetre).getByRole('button', { name: 'Associer à Mars' })).toBeInTheDocument();
    expect(
      within(fenetre).queryByRole('button', { name: 'Associer à Canette de soda' }),
    ).not.toBeInTheDocument();

    // La recherche filtre la liste, sans tenir compte de la casse.
    await user.type(within(fenetre).getByRole('searchbox'), 'kinder');
    expect(
      within(fenetre).queryByRole('button', { name: 'Associer à Mars' }),
    ).not.toBeInTheDocument();

    await user.click(within(fenetre).getByRole('button', { name: 'Associer à KINDER - BUENO' }));

    await waitFor(() => expect(appels).toHaveLength(1));
    // Le code, et rien d'autre : photo, nom et prix restent ceux de HelloAsso.
    expect(appels[0]).toEqual({ barcode: CODE });
    expect(await screen.findByText('Code-barres associé à KINDER - BUENO')).toBeInTheDocument();
    // On scanne en rangeant une livraison : le réappro s'ouvre ensuite.
    expect(
      await screen.findByRole('dialog', { name: 'Réapprovisionner : KINDER - BUENO' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Code-barres inconnu')).not.toBeInTheDocument();
  });

  it('« Créer un nouveau produit » laisse la photo Open Food Facts décochée par défaut', async () => {
    servirProduits();
    servirLookup({
      openfoodfacts: {
        name: 'Kinder Bueno',
        brand: 'Ferrero',
        image_url: 'https://images.openfoodfacts.org/bueno.jpg',
        quantity: null,
        categories: [],
      },
    });
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE_URL}/buvette/products`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...KINDER, id: 99, ...corps });
      }),
    );
    const user = await scannerDepuisLaPage();

    const inconnu = await screen.findByRole('dialog');
    await user.click(within(inconnu).getByRole('button', { name: 'Créer un nouveau produit' }));

    const creation = await screen.findByRole('dialog', { name: 'Nouveau produit (scanné)' });
    const caseOff = within(creation).getByRole('checkbox', {
      name: 'Utiliser la photo Open Food Facts',
    });
    expect(caseOff).not.toBeChecked();
    // Photo non retenue : la vignette n'est pas affichée.
    expect(within(creation).queryByRole('img')).not.toBeInTheDocument();

    await user.click(within(creation).getByRole('button', { name: 'Soumettre' }));
    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps!.image_url).toBeNull();
    expect(corps!.barcode).toBe(CODE);
  });

  it('un produit déjà relié ouvre directement le réappro', async () => {
    servirProduits();
    servirLookup({ found_in: 'buvette', buvette_product: { ...KINDER, barcode: CODE } });
    await scannerDepuisLaPage();

    expect(
      await screen.findByRole('dialog', { name: 'Réapprovisionner : KINDER - BUENO' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Code-barres inconnu')).not.toBeInTheDocument();
  });
});

describe('pages/buvette : code-barres dans la fiche produit', () => {
  async function ouvrirFiche(nom: string) {
    const user = userEvent.setup();
    rendre();
    const titre = await screen.findByText(nom);
    const carte = titre.closest('.flex.flex-col') as HTMLElement;
    await user.click(within(carte).getByRole('button', { name: 'Modifier' }));
    const fenetre = await screen.findByRole('dialog', { name: 'Modifier le produit' });
    return { user, fenetre };
  }

  it('le scan remplit le champ, et seul le code part au serveur', async () => {
    servirProduits();
    const appels = capturerPatch(11, (corps) => ({ ...KINDER, ...corps }));
    const { user, fenetre } = await ouvrirFiche('KINDER - BUENO');

    const champ = within(fenetre).getByLabelText('Code-barres');
    expect(champ).toHaveValue('');
    await user.click(within(fenetre).getByRole('button', { name: 'Scanner' }));
    // Le faux lecteur est rendu sous la fiche, que Radix rend inerte (le vrai
    // lecteur est une fenêtre par-dessus) : clic direct.
    fireEvent.click(await screen.findByRole('button', { name: 'Simuler le scan', hidden: true }));
    expect(within(fenetre).getByLabelText('Code-barres')).toHaveValue(CODE);

    await user.click(within(fenetre).getByRole('button', { name: 'Mettre à jour' }));
    await waitFor(() => expect(appels).toHaveLength(1));
    expect(appels[0]).toEqual({ barcode: CODE });
  });

  it('« Retirer » vide le champ et envoie `barcode: null`', async () => {
    servirProduits();
    const appels = capturerPatch(12, (corps) => ({ ...SODA, ...corps }));
    const { user, fenetre } = await ouvrirFiche('Canette de soda');

    expect(within(fenetre).getByLabelText('Code-barres')).toHaveValue('8000500310427');
    await user.click(within(fenetre).getByRole('button', { name: 'Retirer' }));
    expect(within(fenetre).getByLabelText('Code-barres')).toHaveValue('');

    await user.click(within(fenetre).getByRole('button', { name: 'Mettre à jour' }));
    await waitFor(() => expect(appels).toHaveLength(1));
    expect(appels[0]).toEqual({ barcode: null });
  });

  it('refuse un code mal formé sans rien envoyer', async () => {
    servirProduits();
    const appels = capturerPatch(11, (corps) => ({ ...KINDER, ...corps }));
    const { user, fenetre } = await ouvrirFiche('KINDER - BUENO');

    await user.type(within(fenetre).getByLabelText('Code-barres'), '123');
    await user.click(within(fenetre).getByRole('button', { name: 'Mettre à jour' }));
    expect(
      await within(fenetre).findByText('Code-barres invalide (8 à 14 chiffres).'),
    ).toBeInTheDocument();
    expect(appels).toHaveLength(0);
  });
});

describe('pages/buvette : repérer les produits sans code-barres', () => {
  it('affiche le code sur la carte, et filtre les produits sans code-barres', async () => {
    servirProduits();
    const user = userEvent.setup();
    rendre();

    expect(await screen.findByText('8000500310427')).toBeInTheDocument();
    expect(screen.getAllByText('Sans code-barres', { selector: 'span' })).toHaveLength(2);

    const filtre = screen.getByRole('button', { name: /Sans code-barres \(2\)/ });
    expect(filtre).toHaveAttribute('aria-pressed', 'false');
    await user.click(filtre);
    expect(filtre).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText('Canette de soda')).not.toBeInTheDocument();
    expect(screen.getByText('KINDER - BUENO')).toBeInTheDocument();
    expect(screen.getByText('Mars')).toBeInTheDocument();

    await user.click(filtre);
    expect(screen.getByText('Canette de soda')).toBeInTheDocument();
  });
});
