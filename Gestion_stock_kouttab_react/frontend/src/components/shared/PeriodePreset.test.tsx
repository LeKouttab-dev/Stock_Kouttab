import { describe, expect, it } from 'vitest';
import { http, HttpResponse, type JsonBodyType } from 'msw';
import { server } from '@/test/mocks/server';
import { fireEvent, renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
import { bornesPreset } from '@/lib/periode';
import { StatistiquesTab } from '@/pages/buvette/tabs/StatistiquesTab';
import { PaiementsTab } from '@/pages/buvette/tabs/PaiementsTab';

const BASE_URL = 'http://localhost:8000/api/v1';

function espionner(chemin: string, reponse: JsonBodyType) {
  const appels: URLSearchParams[] = [];
  server.use(
    http.get(`${BASE_URL}${chemin}`, ({ request }) => {
      appels.push(new URL(request.url).searchParams);
      return HttpResponse.json(reponse);
    }),
  );
  return () => appels[appels.length - 1];
}

describe('components/shared/PeriodePreset', () => {
  it('Statistiques : « Ce mois-ci » par défaut, puis chaque préréglage envoie ses dates', async () => {
    const dernier = espionner('/buvette/stats', {
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
    });
    const user = userEvent.setup();
    renderWithProviders(<StatistiquesTab />);

    const mois = bornesPreset('mois');
    await waitFor(() => expect(dernier()?.get('debut')).toBe(mois.debut));
    expect(dernier()?.get('fin')).toBe(mois.fin);
    expect(screen.getByRole('button', { name: 'Ce mois-ci' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.queryByLabelText('Du')).not.toBeInTheDocument();

    for (const [nom, preset] of [
      ['7 derniers jours', '7j'],
      ['3 derniers mois', '3mois'],
      ['Aujourd’hui', 'aujourdhui'],
    ] as const) {
      await user.click(screen.getByRole('button', { name: nom }));
      const attendu = bornesPreset(preset);
      await waitFor(() => expect(dernier()?.get('debut')).toBe(attendu.debut));
      expect(dernier()?.get('fin')).toBe(attendu.fin);
    }

    await user.click(screen.getByRole('button', { name: 'Personnalisé' }));
    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-09-01' } });
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-09-15' } });
    await waitFor(() => expect(dernier()?.get('debut')).toBe('2026-09-01'));
    expect(dernier()?.get('fin')).toBe('2026-09-15');
  });

  it('Paiements : « Aujourd’hui » par défaut', async () => {
    const dernier = espionner('/buvette/paiements', {
      paiements: [],
      totaux: {
        carte_cents: 0,
        especes_cents: 0,
        helloasso_cents: 0,
        total_cents: 0,
        nb_ventes: 0,
      },
    });
    renderWithProviders(<PaiementsTab />);
    const jour = bornesPreset('aujourdhui');
    await waitFor(() => expect(dernier()?.get('debut')).toBe(jour.debut));
    expect(dernier()?.get('fin')).toBe(jour.fin);
    expect(screen.getByRole('button', { name: 'Aujourd’hui' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});
