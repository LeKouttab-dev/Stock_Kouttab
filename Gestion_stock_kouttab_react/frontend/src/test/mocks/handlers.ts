import { http, HttpResponse } from 'msw';
import type { LoginResponse, StockItem, User } from '@/types/api';

const BASE_URL = 'http://localhost:8000/api/v1';

/* ---------- Fixtures ---------- */
export const mockUser: User = {
  id: 1,
  username: 'testuser',
  role: 'Super Admin',
  validation_status: 'active',
  nom: 'Doe',
  prenom: 'John',
  email: 'john@example.com',
  telephone: null,
  rib: null,
};

export const mockLoginResponse: LoginResponse = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  user: mockUser,
};

export const mockStockItems: StockItem[] = [
  {
    id: 1,
    nom: 'Café',
    categorie: 'Nourriture',
    sous_categorie: 'Boissons',
    quantite: 12,
    seuil_alerte: 5,
    emoji: '☕',
    alert_sent: false,
  },
  {
    id: 2,
    nom: 'Cahiers',
    categorie: 'Fournitures',
    sous_categorie: null,
    quantite: 2,
    seuil_alerte: 5,
    emoji: '📓',
    alert_sent: false,
  },
];

/* ---------- Handlers ---------- */
export const handlers = [
  // ----- Auth -----
  http.post(`${BASE_URL}/auth/login/json`, async () => {
    return HttpResponse.json(mockLoginResponse);
  }),

  http.post(`${BASE_URL}/auth/signup`, async () => {
    return HttpResponse.json({ message: 'Compte créé. En attente de validation.' });
  }),

  http.get(`${BASE_URL}/auth/me`, () => HttpResponse.json(mockUser)),

  http.post(`${BASE_URL}/auth/logout`, () => HttpResponse.json({ ok: true })),

  http.post(`${BASE_URL}/auth/refresh`, () =>
    HttpResponse.json({ access_token: 'refreshed-token', refresh_token: 'refreshed-refresh' }),
  ),

  // ----- Stock -----
  http.get(`${BASE_URL}/stock/items`, () => HttpResponse.json(mockStockItems)),

  http.post(`${BASE_URL}/stock/items`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 99,
      alert_sent: false,
      ...body,
    });
  }),

  http.patch(`${BASE_URL}/stock/items/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...mockStockItems[0], ...body, id: Number(params.id) });
  }),

  http.delete(`${BASE_URL}/stock/items/:id`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE_URL}/stock/categories`, () =>
    HttpResponse.json([
      { nom: 'Nourriture', is_default: true },
      { nom: 'Fournitures', is_default: true },
    ]),
  ),

  http.get(`${BASE_URL}/stock/subcategories`, () =>
    HttpResponse.json([{ id: 1, nom_categorie: 'Nourriture', nom_sous_categorie: 'Boissons' }]),
  ),

  http.get(`${BASE_URL}/stock/statistics`, () =>
    HttpResponse.json({
      total_articles: 2,
      total_quantite: 14,
      alertes_stock: 1,
      stock_epuise: 0,
      stats_par_categorie: [],
      stats_nourriture_sous_categories: [],
      dernieres_modifs: [],
    }),
  ),

  http.get(`${BASE_URL}/stock/low-stock`, () => HttpResponse.json([mockStockItems[1]])),

  http.get(`${BASE_URL}/stock/modifications`, () => HttpResponse.json([])),

  // ----- Expenses -----
  http.get(`${BASE_URL}/expenses/me`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/expenses`, () => HttpResponse.json([])),

  // ----- Invoices -----
  http.get(`${BASE_URL}/invoices/me`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/invoices`, () => HttpResponse.json([])),

  // ----- Users -----
  http.get(`${BASE_URL}/users`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/users/pending`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/users/me/profile`, () => HttpResponse.json(mockUser)),

  // ----- Buvette -----
  http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json([])),
  // Fiche d'un produit : le serveur renvoie le produit à jour. Par défaut, on
  // renvoie le corps reçu (les tests qui vérifient l'envoi le surchargent).
  http.patch(`${BASE_URL}/buvette/products/:id`, async ({ params, request }) => {
    const corps = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: Number(params.id), ...corps });
  }),
  // Code-barres inconnu partout, sans fiche Open Food Facts.
  http.get(`${BASE_URL}/stock/lookup-barcode/:code`, ({ params }) =>
    HttpResponse.json({
      barcode: String(params.code),
      found_in: null,
      stock_item: null,
      buvette_product: null,
      openfoodfacts: null,
    }),
  ),
  http.get(`${BASE_URL}/buvette/sales`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/buvette/webhook/status`, () =>
    HttpResponse.json({
      url_a_enregistrer: null,
      url: null,
      configured: null,
      verifiable: false,
      last_sale_at: null,
      sales_count: 0,
    }),
  ),
  http.get(`${BASE_URL}/buvette/paiements`, () =>
    HttpResponse.json({
      paiements: [],
      totaux: {
        carte_cents: 0,
        especes_cents: 0,
        helloasso_cents: 0,
        total_cents: 0,
        frais_carte_cents: 0,
        carte_net_cents: 0,
        net_total_cents: 0,
        nb_ventes: 0,
        taux_frais_carte_pb: 170,
      },
    }),
  ),
  http.get(`${BASE_URL}/buvette/reapprovisionnements`, () =>
    HttpResponse.json({ reappros: [], totaux: { nb: 0, quantite: 0, montant_cents: 0 } }),
  ),
  http.get(`${BASE_URL}/buvette/stats`, () =>
    HttpResponse.json({
      totaux: {
        ca_cents: 0,
        frais_carte_cents: 0,
        net_cents: 0,
        ventes: 0,
        taux_frais_carte_pb: 170,
      },
      par_jour: [],
      par_heure: [],
      par_produit: [],
      par_moyen: [],
    }),
  ),
  http.get(`${BASE_URL}/buvette/clotures/attendu`, () =>
    HttpResponse.json({
      periode_debut: null,
      periode_fin: '2026-10-10T10:00:00Z',
      premier_comptage: true,
      attendu_cents: 0,
      nb_ventes: 0,
      ventes: [],
      dernier_comptage: null,
    }),
  ),
  http.get(`${BASE_URL}/buvette/clotures`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/buvette/inventaires/en-cours`, () =>
    HttpResponse.json({ inventaire: null }),
  ),
  http.get(`${BASE_URL}/buvette/inventaires`, () => HttpResponse.json([])),
  http.get(`${BASE_URL}/buvette/caisse/etat`, () => HttpResponse.json({ etat: null })),
  http.get(`${BASE_URL}/buvette/reglages`, () =>
    HttpResponse.json({
      recap_destinataires: [],
      comptes_admin_stock: [],
      taux_frais_carte_pb: 170,
    }),
  ),
];
