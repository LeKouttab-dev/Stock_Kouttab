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
import type { Cloture, ClotureAttendu, DernierComptage } from '@/types/api';
import { ClotureTab } from '../tabs/ClotureTab';
import { BASE_URL, connecter } from './helpers';

const VENTES = [
  {
    cle: 'tx-1',
    sold_at: '2026-10-09T16:40:00Z',
    total_cents: 500,
    articles: [{ nom: 'Gâteau', quantite: 2, montant_cents: 500 }],
  },
];

function attendu(
  cents: number,
  dernier: DernierComptage | null = { type: 'cloture', le: '2026-10-08T20:15:00Z' },
) {
  let params: URLSearchParams | null = null;
  server.use(
    http.get(`${BASE_URL}/buvette/clotures/attendu`, ({ request }) => {
      params = new URL(request.url).searchParams;
      const debut = params.get('debut');
      const premier = dernier === null;
      const corps: ClotureAttendu = {
        periode_debut: premier && !debut ? null : '2026-10-08T20:15:00Z',
        periode_fin: '2026-10-10T10:00:00Z',
        premier_comptage: premier,
        attendu_cents: premier && !debut ? 0 : cents,
        nb_ventes: premier && !debut ? 0 : VENTES.length,
        ventes: premier && !debut ? [] : VENTES,
        dernier_comptage: dernier,
      };
      return HttpResponse.json(corps);
    }),
  );
  return () => params;
}

function cloture(surcharges: Partial<Cloture> = {}): Cloture {
  return {
    id: 1,
    jour: '2026-10-09',
    periode_debut: '2026-10-08T20:15:00Z',
    periode_fin: '2026-10-09T20:10:00Z',
    attendu_cents: 4250,
    compte_cents: 4000,
    ecart_cents: -250,
    nb_ventes: 7,
    commentaire: 'Pièce perdue',
    saisi_par: 'Omar',
    created_at: '2026-10-09T20:10:00Z',
    ...surcharges,
  };
}

describe('pages/buvette/tabs/ClotureTab', () => {
  it('affiche la période depuis le dernier comptage et ses ventes en espèces', async () => {
    attendu(4250);
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    expect(await screen.findByTestId('cloture-depuis')).toHaveTextContent(
      'Depuis le dernier comptage (clôture du 08/10/2026 22:15)',
    );
    expect(screen.getByTestId('attendu')).toHaveTextContent('42.50 €');
    expect(screen.getByText('2 × Gâteau')).toBeInTheDocument();
    expect(screen.getByText('09/10/2026 18:40')).toBeInTheDocument();
    expect(screen.queryByLabelText('Ventes en espèces depuis le')).not.toBeInTheDocument();
    expect(screen.getByText('La boîte doit être vidée après le comptage.')).toBeInTheDocument();
  });

  it('annonce un inventaire comme dernier comptage', async () => {
    attendu(1000, { type: 'inventaire', le: '2026-10-07T18:00:00Z' });
    renderWithProviders(<ClotureTab />);
    expect(await screen.findByTestId('cloture-depuis')).toHaveTextContent(
      'Depuis le dernier comptage (inventaire du 07/10/2026 20:00)',
    );
  });

  it("calcule l'écart à la saisie et le colore selon son ampleur", async () => {
    attendu(4250);
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    const champ = await screen.findByLabelText('Espèces comptées (€)');
    await user.type(champ, '40');
    let ecart = screen.getByTestId('ecart');
    expect(ecart).toHaveTextContent('−2,50 €');
    expect(ecart).toHaveAttribute('data-ton', 'leger');

    await user.clear(champ);
    await user.type(champ, '60');
    ecart = screen.getByTestId('ecart');
    expect(ecart).toHaveTextContent('+17,50 €');
    expect(ecart).toHaveAttribute('data-ton', 'fort');
  });

  it('premier comptage : demande la date de début et l’envoie', async () => {
    const lireParams = attendu(1200, null);
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE_URL}/buvette/clotures`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(cloture(), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    expect(
      await screen.findByText('Choisissez une date pour afficher les ventes.'),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Ventes en espèces depuis le'), {
      target: { value: '2026-09-01' },
    });
    await waitFor(() => expect(lireParams()?.get('debut')).toBe('2026-09-01'));
    expect(await screen.findByTestId('attendu')).toHaveTextContent('12.00 €');

    await user.type(screen.getByLabelText('Espèces comptées (€)'), '12');
    await user.click(screen.getByRole('button', { name: /Clôturer et vider la boîte/ }));
    await user.click(await screen.findByRole('button', { name: /^Clôturer$/ }));

    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps).toMatchObject({ compte_cents: 1200, debut: '2026-09-01' });
  });

  it('demande une confirmation avant de clôturer, puis envoie le montant en centimes', async () => {
    attendu(4250);
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE_URL}/buvette/clotures`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(cloture(), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    await user.type(await screen.findByLabelText('Espèces comptées (€)'), '41,9');
    await user.type(screen.getByLabelText('Commentaire (facultatif)'), 'Pièce perdue');
    await user.click(screen.getByRole('button', { name: /Clôturer et vider la boîte/ }));

    const dialogue = await screen.findByRole('dialog');
    expect(within(dialogue).getByText(/Espèces comptées : 41.90 €/)).toBeInTheDocument();
    // Annuler n'envoie rien.
    await user.click(within(dialogue).getByRole('button', { name: 'Annuler' }));
    expect(corps).toBeNull();

    await user.click(screen.getByRole('button', { name: /Clôturer et vider la boîte/ }));
    await user.click(await screen.findByRole('button', { name: /^Clôturer$/ }));
    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps).toEqual({ compte_cents: 4190, commentaire: 'Pièce perdue', debut: null });
  });

  it('refuse une saisie qui n’est pas un montant', async () => {
    attendu(1000);
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('Super Admin');

    await user.type(await screen.findByLabelText('Espèces comptées (€)'), '12abc');
    expect(screen.getByText(/Saisissez un montant en euros/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clôturer et vider la boîte/ })).toBeDisabled();
  });

  it('la comptabilité consulte sans pouvoir clôturer', async () => {
    attendu(1000);
    renderWithProviders(<ClotureTab />);
    connecter('Compta');
    expect(
      await screen.findByText('Seuls les gestionnaires de la buvette peuvent clôturer la caisse.'),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText('Espèces comptées (€)')).not.toBeInTheDocument();
  });

  it('filtre l’historique par période et l’exporte avec les mêmes filtres', async () => {
    attendu(0);
    window.URL.createObjectURL = vi.fn(() => 'blob:clotures');
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
      http.get(`${BASE_URL}/buvette/clotures`, ({ request }) => {
        paramsListe = new URL(request.url).searchParams;
        return HttpResponse.json([cloture()]);
      }),
      http.get(`${BASE_URL}/buvette/clotures/export.xlsx`, ({ request }) => {
        paramsExport = new URL(request.url).searchParams;
        return new HttpResponse(new Blob(['xlsx']));
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    const ligne = await screen.findByTestId('cloture-ligne');
    expect(ligne).toHaveTextContent('du 08/10/2026 22:15 au 09/10/2026 22:10');
    expect(ligne).toHaveTextContent('Pièce perdue');
    expect(within(ligne).getByTestId('ecart')).toHaveTextContent('−2,50 €');

    await selectionnerPeriodePersonnalisee(user, '2026-10-01', '2026-10-09');
    await waitFor(() => expect(paramsListe?.get('debut')).toBe('2026-10-01'));
    expect((paramsListe as unknown as URLSearchParams).get('fin')).toBe('2026-10-09');

    await user.click(screen.getByRole('button', { name: /Exporter \(Excel\)/ }));
    await waitFor(() => expect(clic).toHaveBeenCalledTimes(1));
    const p = paramsExport as unknown as URLSearchParams;
    expect(p.get('debut')).toBe('2026-10-01');
    expect(p.get('fin')).toBe('2026-10-09');
    expect(noms[0]).toBe('clotures-2026-10-01_2026-10-09.xlsx');
    clic.mockRestore();
  });
});

async function selectionnerPeriodePersonnalisee(
  user: ReturnType<typeof userEvent.setup>,
  debut: string,
  fin: string,
) {
  await user.click(screen.getByRole('button', { name: 'Personnalisé' }));
  fireEvent.change(screen.getByLabelText('Du'), { target: { value: debut } });
  fireEvent.change(screen.getByLabelText('Au'), { target: { value: fin } });
}
