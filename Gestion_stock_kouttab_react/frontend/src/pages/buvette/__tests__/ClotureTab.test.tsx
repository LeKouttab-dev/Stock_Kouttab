import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, userEvent, waitFor } from '@/test/test-utils';
import type { Cloture } from '@/types/api';
import { ClotureTab } from '../tabs/ClotureTab';
import { BASE_URL, connecter } from './helpers';

function attendu(cents: number, cloture: Cloture | null = null) {
  server.use(
    http.get(`${BASE_URL}/buvette/clotures/attendu`, ({ request }) =>
      HttpResponse.json({
        jour: new URL(request.url).searchParams.get('jour'),
        attendu_cents: cents,
        nb_ventes_especes: 3,
        cloture,
      }),
    ),
  );
}

describe('pages/buvette/tabs/ClotureTab', () => {
  it("calcule l'écart à la saisie et le colore selon son ampleur", async () => {
    attendu(4250);
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    expect(await screen.findByTestId('attendu')).toHaveTextContent('42.50 €');
    const champ = await screen.findByLabelText('Montant compté (€)');

    await user.type(champ, '40');
    let ecart = screen.getByTestId('ecart');
    expect(ecart).toHaveTextContent('−2,50 €');
    expect(ecart).toHaveAttribute('data-ton', 'leger');
    expect(ecart).toHaveClass('text-orange-600');

    await user.clear(champ);
    await user.type(champ, '42,50');
    ecart = screen.getByTestId('ecart');
    expect(ecart).toHaveTextContent('0,00 €');
    expect(ecart).toHaveAttribute('data-ton', 'juste');

    await user.clear(champ);
    await user.type(champ, '60');
    ecart = screen.getByTestId('ecart');
    expect(ecart).toHaveTextContent('+17,50 €');
    expect(ecart).toHaveAttribute('data-ton', 'fort');
    expect(ecart).toHaveClass('text-red-700');
  });

  it('envoie le montant compté en centimes', async () => {
    attendu(4250);
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE_URL}/buvette/clotures`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    await user.type(await screen.findByLabelText('Montant compté (€)'), '41,9');
    await user.type(screen.getByLabelText('Commentaire (facultatif)'), 'Pièce perdue');
    await user.click(screen.getByRole('button', { name: /Clôturer/ }));

    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps).toMatchObject({ compte_cents: 4190, commentaire: 'Pièce perdue' });
  });

  it('refuse une saisie qui n’est pas un montant', async () => {
    attendu(1000);
    const user = userEvent.setup();
    renderWithProviders(<ClotureTab />);
    connecter('Super Admin');

    await user.type(await screen.findByLabelText('Montant compté (€)'), '12abc');
    expect(screen.getByText(/Saisissez un montant en euros/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Clôturer/ })).toBeDisabled();
  });

  it('montre un jour déjà clôturé en lecture seule', async () => {
    attendu(4250, {
      id: 1,
      jour: '2026-10-09',
      attendu_cents: 4250,
      compte_cents: 4000,
      ecart_cents: -250,
      commentaire: null,
      saisi_par: 'Omar',
      created_at: '2026-10-09T22:10:00',
    });
    renderWithProviders(<ClotureTab />);
    connecter('AdminStock');

    expect(await screen.findByText('Ce jour est déjà clôturé.')).toBeInTheDocument();
    expect(screen.getByTestId('ecart')).toHaveTextContent('−2,50 €');
    expect(screen.queryByLabelText('Montant compté (€)')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Clôturer/ })).not.toBeInTheDocument();
  });
});
