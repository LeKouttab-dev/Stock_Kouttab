import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/test-utils';
import { LoginPage } from './LoginPage';
import { ERROR_MESSAGES } from '@/lib/errors';
import { mockLoginResponse } from '@/test/mocks/handlers';

const BASE_URL = 'http://localhost:8000/api/v1';

function renderLogin(initialPath = '/login') {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<div>SIGNUP_PAGE</div>} />
      <Route path="/dashboard" element={<div>DASHBOARD_PAGE</div>} />
    </Routes>,
    { routerEntries: [initialPath] },
  );
}

describe('pages/auth/LoginPage', () => {
  it('renders empty fields and a "Se connecter" button initially', () => {
    renderLogin();

    expect(screen.getByLabelText(/Nom d'utilisateur/i)).toHaveValue('');
    expect(screen.getByLabelText(/^Mot de passe/i)).toHaveValue('');
    // Le bouton submit + le lien partagent le label "Se connecter" → on cherche le bouton
    expect(screen.getByRole('button', { name: /Se connecter/i })).toBeInTheDocument();
  });

  it('shows Zod validation errors when submitting empty fields', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole('button', { name: /Se connecter/i }));

    expect(await screen.findByText(/Au moins 3 caractères/i)).toBeInTheDocument();
    expect(screen.getByText(/Champ obligatoire/)).toBeInTheDocument();
  });

  it('accepts an email address as the identifier', async () => {
    // Les bénévoles retiennent leur adresse, rarement leur identifiant. Le
    // formulaire bornait la saisie à 20 caractères — celle d'un identifiant —
    // et rejetait donc toute adresse avant même d'appeler l'API.
    let envoye: unknown = null;
    server.use(
      http.post(`${BASE_URL}/auth/login/json`, async ({ request }) => {
        envoye = await request.json();
        return HttpResponse.json(mockLoginResponse);
      }),
    );

    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Nom d'utilisateur/i), 'benfdila.omir@gmail.com');
    await user.type(screen.getByLabelText(/^Mot de passe/i), 'Admin1234!');
    await user.click(screen.getByRole('button', { name: /Se connecter/i }));

    await waitFor(() => expect(envoye).not.toBeNull());
    expect((envoye as { username: string }).username).toBe('benfdila.omir@gmail.com');
  });

  it('offers a link to reset a forgotten password', () => {
    renderLogin();
    expect(screen.getByRole('link', { name: /Mot de passe oublié/i })).toBeInTheDocument();
  });

  it('redirects to /dashboard on successful login', async () => {
    // Default handler returns 200 with mock user — perfect.
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Nom d'utilisateur/i), 'admin');
    await user.type(screen.getByLabelText(/^Mot de passe/i), 'Admin1234!');
    await user.click(screen.getByRole('button', { name: /Se connecter/i }));

    await waitFor(
      () => {
        expect(screen.getByText('DASHBOARD_PAGE')).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it('renders an ErrorAlert with the AUTH_1001 message on 401', async () => {
    server.use(
      http.post(`${BASE_URL}/auth/login/json`, () =>
        HttpResponse.json(
          { code: 'AUTH_1001', message: 'Identifiants invalides' },
          { status: 401 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Nom d'utilisateur/i), 'admin');
    await user.type(screen.getByLabelText(/^Mot de passe/i), 'wrongpw1!');
    await user.click(screen.getByRole('button', { name: /Se connecter/i }));

    expect(await screen.findByText(ERROR_MESSAGES.AUTH_1001)).toBeInTheDocument();
    expect(screen.getByText('Connexion refusée')).toBeInTheDocument();
  });

  it('navigates to /signup when clicking "Créer un compte"', async () => {
    const user = userEvent.setup();
    renderLogin();

    const link = screen.getByRole('link', { name: /Créer un compte/i });
    await user.click(link);

    expect(await screen.findByText('SIGNUP_PAGE')).toBeInTheDocument();
  });
});

// Silence noisy axios console.warn in tests (interceptor logs in DEV)
vi.spyOn(console, 'warn').mockImplementation(() => {});
