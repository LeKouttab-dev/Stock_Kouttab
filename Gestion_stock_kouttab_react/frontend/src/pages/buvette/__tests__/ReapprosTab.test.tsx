import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { fireEvent, renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
import { periodeGlissante } from '@/lib/buvette';
import type { BuvetteProduct, ReapprosResponse } from '@/types/api';
import { ReapprosTab } from '../tabs/ReapprosTab';
import { BASE_URL } from './helpers';

const PRODUIT = (id: number, name: string): BuvetteProduct => ({
  id,
  helloasso_tier_id: null,
  name,
  description: null,
  price_cents: 150,
  quantity: 10,
  seuil_alerte: 2,
  emoji: '☕',
  image_url: null,
  is_active: true,
  alert_sent: false,
  last_synced_at: null,
  low_stock: false,
});

const REPONSE: ReapprosResponse = {
  reappros: [
    {
      id: 2,
      product_id: 7,
      nom: 'Café',
      quantite: 60,
      prix_achat_unitaire_cents: 45,
      total_cents: 2700,
      origine: 'app',
      commentaire: 'Livraison Metro',
      fait_par: 'Omar',
      stock_avant: 15,
      stock_apres: 75,
      created_at: '2026-10-09T08:30:00Z',
    },
    {
      id: 1,
      product_id: 8,
      nom: 'Thé',
      quantite: 10,
      prix_achat_unitaire_cents: null,
      total_cents: null,
      origine: 'tablette',
      commentaire: null,
      fait_par: 'tablette',
      stock_avant: 3,
      stock_apres: 13,
      created_at: '2026-10-08T17:05:00Z',
    },
  ],
  totaux: { nb: 2, quantite: 70, montant_cents: 2700 },
};

function servirProduits() {
  server.use(
    http.get(`${BASE_URL}/buvette/products`, () =>
      HttpResponse.json([PRODUIT(7, 'Café'), PRODUIT(8, 'Thé')]),
    ),
  );
}

describe('pages/buvette/tabs/ReapprosTab', () => {
  it('affiche les totaux et une ligne par réappro, sur 30 jours par défaut', async () => {
    servirProduits();
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/reapprovisionnements`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return HttpResponse.json(REPONSE);
      }),
    );
    renderWithProviders(<ReapprosTab />);

    expect(await screen.findByText('Livraison Metro')).toBeInTheDocument();
    expect(screen.getByTestId('reappros-nb')).toHaveTextContent('2');
    expect(screen.getByTestId('reappros-quantite')).toHaveTextContent('70');
    expect(screen.getByTestId('reappros-montant')).toHaveTextContent('27.00 €');
    // Heure de Paris : 08:30 UTC = 10:30.
    expect(screen.getByText('09/10/2026 10:30')).toBeInTheDocument();
    expect(screen.getByText('+60')).toBeInTheDocument();
    expect(screen.getByText('0.45 €')).toBeInTheDocument();
    expect(screen.getByText('non renseigné')).toBeInTheDocument();
    expect(screen.getByText('App stock')).toBeInTheDocument();
    expect(screen.getByText('15 → 75')).toBeInTheDocument();
    expect(screen.getByText('3 → 13')).toBeInTheDocument();

    await waitFor(() => expect(params).not.toBeNull());
    const p = params as unknown as URLSearchParams;
    const defaut = periodeGlissante(30);
    expect(p.get('debut')).toBe(defaut.debut);
    expect(p.get('fin')).toBe(defaut.fin);
    expect(p.get('product_id')).toBeNull();
    expect(p.get('origine')).toBeNull();
  });

  it('annonce une période sans réappro', async () => {
    renderWithProviders(<ReapprosTab />);
    expect(
      await screen.findByText('Aucun réapprovisionnement sur cette période.'),
    ).toBeInTheDocument();
  });

  it('filtre par période, produit et origine, et exporte avec les mêmes filtres', async () => {
    servirProduits();
    window.URL.createObjectURL = vi.fn(() => 'blob:reappros');
    window.URL.revokeObjectURL = vi.fn();
    const noms: string[] = [];
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      noms.push(this.download);
    });
    let paramsListe: URLSearchParams | null = null;
    let paramsExport: URLSearchParams | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/reapprovisionnements`, ({ request }) => {
        paramsListe = new URL(request.url).searchParams;
        return HttpResponse.json(REPONSE);
      }),
      http.get(`${BASE_URL}/buvette/reapprovisionnements/export.xlsx`, ({ request }) => {
        paramsExport = new URL(request.url).searchParams;
        return new HttpResponse(new Blob(['xlsx']), {
          headers: {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ReapprosTab />);

    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-10-01' } });
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-10-09' } });
    await user.click(screen.getByLabelText('Produit'));
    await user.click(await screen.findByRole('option', { name: 'Thé' }));
    await user.click(screen.getByLabelText('Origine'));
    await user.click(await screen.findByRole('option', { name: 'Tablette' }));

    await waitFor(() => expect(paramsListe?.get('origine')).toBe('tablette'));
    const l = paramsListe as unknown as URLSearchParams;
    expect(l.get('debut')).toBe('2026-10-01');
    expect(l.get('fin')).toBe('2026-10-09');
    expect(l.get('product_id')).toBe('8');

    await user.click(screen.getByRole('button', { name: /Exporter \(Excel\)/ }));
    await waitFor(() => expect(clic).toHaveBeenCalledTimes(1));
    const p = paramsExport as unknown as URLSearchParams;
    expect(p.get('debut')).toBe('2026-10-01');
    expect(p.get('fin')).toBe('2026-10-09');
    expect(p.get('product_id')).toBe('8');
    expect(p.get('origine')).toBe('tablette');
    // Pas de nom annoncé : nom par défaut, calqué sur celui du serveur.
    expect(noms[0]).toBe('reapprovisionnements-2026-10-01_2026-10-09.xlsx');
    clic.mockRestore();
  });
});
