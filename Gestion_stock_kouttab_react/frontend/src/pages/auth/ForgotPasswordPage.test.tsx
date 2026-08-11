import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/test-utils';
import { ForgotPasswordPage } from './ForgotPasswordPage';

const BASE_URL = 'http://localhost:8000/api/v1';

function render() {
  return renderWithProviders(
    <Routes>
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/login" element={<div>LOGIN_PAGE</div>} />
    </Routes>,
    { routerEntries: ['/forgot-password'] },
  );
}

describe('pages/auth/ForgotPasswordPage', () => {
  it('envoie l’identifiant saisi et confirme', async () => {
    let envoye: unknown = null;
    server.use(
      http.post(`${BASE_URL}/auth/forgot-password`, async ({ request }) => {
        envoye = await request.json();
        return HttpResponse.json({ message: 'ok' });
      }),
    );

    const user = userEvent.setup();
    render();

    await user.type(screen.getByLabelText(/utilisateur/i), 'benevole@example.com');
    await user.click(screen.getByRole('button', { name: /Envoyer le lien/i }));

    await waitFor(() => expect(envoye).not.toBeNull());
    expect(envoye).toEqual({ identifiant: 'benevole@example.com' });
    expect(await screen.findByText(/un lien vient d'être envoyé/i)).toBeInTheDocument();
  });

  it('affiche la même confirmation pour un compte inconnu', async () => {
    // L'écran ne doit pas révéler si le compte existe : le serveur répond la
    // même chose dans les deux cas, l'interface ne doit pas le contredire.
    server.use(
      http.post(`${BASE_URL}/auth/forgot-password`, () => HttpResponse.json({ message: 'ok' })),
    );

    const user = userEvent.setup();
    render();

    await user.type(screen.getByLabelText(/utilisateur/i), 'inconnu');
    await user.click(screen.getByRole('button', { name: /Envoyer le lien/i }));

    expect(await screen.findByText(/un lien vient d'être envoyé/i)).toBeInTheDocument();
  });

  it('refuse une saisie trop courte sans appeler l’API', async () => {
    const appele = { valeur: false };
    server.use(
      http.post(`${BASE_URL}/auth/forgot-password`, () => {
        appele.valeur = true;
        return HttpResponse.json({ message: 'ok' });
      }),
    );

    const user = userEvent.setup();
    render();

    await user.type(screen.getByLabelText(/utilisateur/i), 'ab');
    await user.click(screen.getByRole('button', { name: /Envoyer le lien/i }));

    expect(await screen.findByText(/Au moins 3 caractères/i)).toBeInTheDocument();
    expect(appele.valeur).toBe(false);
  });
});
