import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
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
};

function servirProduits() {
  server.use(http.get(`${BASE_URL}/buvette/products`, () => HttpResponse.json([CAFE])));
}

describe('pages/buvette/BuvettePage : réappro', () => {
  it('ajoute le palier choisi au stock et annonce le nouveau stock', async () => {
    servirProduits();
    let corps: unknown = null;
    server.use(
      http.post(`${BASE_URL}/buvette/products/7/reappro`, async ({ request }) => {
        corps = await request.json();
        return HttpResponse.json({ ...CAFE, quantity: 22 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <BuvettePage />
        <Toaster />
      </>,
      { routerEntries: ['/buvette'] },
    );
    connecter('AdminStock');

    const bouton = await screen.findByRole('button', { name: 'Ajouter 10 au stock' });
    for (const n of [5, 15, 20, 30]) {
      expect(screen.getByRole('button', { name: `Ajouter ${n} au stock` })).toBeInTheDocument();
    }
    await user.click(bouton);

    await waitFor(() => expect(corps).toEqual({ delta: 10 }));
    expect(await screen.findByText('Stock : 22')).toBeInTheDocument();
  });

  it('ne propose pas la réappro à la comptabilité (lecture seule)', async () => {
    servirProduits();
    renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette'] });
    connecter('Compta');

    expect(await screen.findByText('Café')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /au stock$/ })).not.toBeInTheDocument();
  });

  it("ouvre l'onglet indiqué dans l'adresse", async () => {
    renderWithProviders(<BuvettePage />, { routerEntries: ['/buvette?onglet=paiements'] });
    connecter('Super Admin');

    expect(await screen.findByText('Total encaissé')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Paiements/ })).toHaveAttribute('aria-selected', 'true');
  });
});
