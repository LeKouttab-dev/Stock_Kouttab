import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { fireEvent, renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
import type { PaiementsResponse } from '@/types/api';
import { PaiementsTab } from '../tabs/PaiementsTab';
import { BASE_URL } from './helpers';

const REPONSE: PaiementsResponse = {
  paiements: [
    {
      cle: 'tx-1',
      moyen: 'carte',
      sold_at: '2026-10-09T18:42:00',
      total_cents: 450,
      sumup_tx_code: 'TBX9QK',
      helloasso_order_id: null,
      client: null,
      articles: [
        { nom: 'Café', quantite: 2, montant_cents: 300 },
        { nom: 'Gâteau', quantite: 1, montant_cents: 150 },
      ],
    },
    {
      cle: 'ha-123',
      moyen: 'helloasso',
      sold_at: '2026-10-09T12:05:00',
      total_cents: 200,
      sumup_tx_code: null,
      helloasso_order_id: 123,
      client: 'Yanis B.',
      articles: [{ nom: 'Thé', quantite: 2, montant_cents: 200 }],
    },
  ],
  totaux: {
    carte_cents: 450,
    especes_cents: 0,
    helloasso_cents: 200,
    total_cents: 650,
    nb_ventes: 2,
  },
};

describe('pages/buvette/tabs/PaiementsTab', () => {
  it('affiche les totaux et une ligne par paiement, du jour par défaut', async () => {
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/paiements`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return HttpResponse.json(REPONSE);
      }),
    );
    renderWithProviders(<PaiementsTab />);

    expect(await screen.findByText('6.50 €')).toBeInTheDocument();
    expect(screen.getByText('2 vente(s)')).toBeInTheDocument();
    expect(screen.getByText('TBX9QK')).toBeInTheDocument();
    expect(screen.getByText('Commande 123')).toBeInTheDocument();
    expect(screen.getByText('Yanis B.')).toBeInTheDocument();
    // Badge du moyen + carte KPI « Carte ».
    expect(screen.getAllByText('Carte').length).toBeGreaterThanOrEqual(2);

    await waitFor(() => expect(params).not.toBeNull());
    const p = params as unknown as URLSearchParams;
    expect(p.get('debut')).toBe(p.get('fin'));
    expect(p.get('moyen')).toBeNull();
  });

  it('déplie le détail des articles, puis le replie', async () => {
    server.use(http.get(`${BASE_URL}/buvette/paiements`, () => HttpResponse.json(REPONSE)));
    const user = userEvent.setup();
    renderWithProviders(<PaiementsTab />);

    await screen.findByText('TBX9QK');
    expect(screen.queryByText('1 × Gâteau')).not.toBeInTheDocument();

    const boutons = screen.getAllByRole('button', { name: 'Afficher le détail' });
    await user.click(boutons[0]);

    expect(screen.getByText('2 × Café')).toBeInTheDocument();
    expect(screen.getByText('1 × Gâteau')).toBeInTheDocument();
    expect(screen.queryByText('2 × Thé')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Masquer le détail' }));
    expect(screen.queryByText('2 × Café')).not.toBeInTheDocument();
  });

  it('annonce une période sans paiement', async () => {
    renderWithProviders(<PaiementsTab />);
    expect(await screen.findByText('Aucun paiement sur cette période.')).toBeInTheDocument();
  });

  it('exporte en Excel avec exactement les filtres affichés', async () => {
    window.URL.createObjectURL = vi.fn(() => 'blob:paiements');
    window.URL.revokeObjectURL = vi.fn();
    const noms: string[] = [];
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      noms.push(this.download);
    });
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/paiements/export.xlsx`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return new HttpResponse(new Blob(['xlsx']), {
          headers: {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': 'attachment; filename="paiements-2026-10-01_2026-10-09.xlsx"',
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PaiementsTab />);

    fireEvent.click(screen.getByRole('button', { name: 'Personnalisé' }));

    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-10-01' } });
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-10-09' } });
    await user.click(screen.getByLabelText('Moyen de paiement'));
    await user.click(await screen.findByRole('option', { name: 'Espèces' }));

    await user.click(screen.getByRole('button', { name: /Exporter \(Excel\)/ }));
    await waitFor(() => expect(clic).toHaveBeenCalledTimes(1));
    const p = params as unknown as URLSearchParams;
    expect(p.get('debut')).toBe('2026-10-01');
    expect(p.get('fin')).toBe('2026-10-09');
    expect(p.get('moyen')).toBe('especes');
    expect(noms[0]).toBe('paiements-2026-10-01_2026-10-09.xlsx');
    clic.mockRestore();
  });

  it('exporte sans moyen quand « Tous les moyens » est affiché', async () => {
    window.URL.createObjectURL = vi.fn(() => 'blob:paiements');
    window.URL.revokeObjectURL = vi.fn();
    const noms: string[] = [];
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      noms.push(this.download);
    });
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/paiements/export.xlsx`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return new HttpResponse(new Blob(['xlsx']));
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PaiementsTab />);

    await user.click(screen.getByRole('button', { name: /Exporter \(Excel\)/ }));
    await waitFor(() => expect(clic).toHaveBeenCalledTimes(1));
    const p = params as unknown as URLSearchParams;
    expect(p.get('moyen')).toBeNull();
    expect(p.get('debut')).toBe(p.get('fin'));
    // Pas de nom annoncé : nom par défaut construit sur la période.
    expect(noms[0]).toBe(`paiements-${p.get('debut')}_${p.get('fin')}.xlsx`);
    clic.mockRestore();
  });
});
