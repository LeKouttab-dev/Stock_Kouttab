import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { server } from '@/test/mocks/server';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/test-utils';
import { SignupPage } from './SignupPage';
import { ERROR_MESSAGES } from '@/lib/errors';

const BASE_URL = 'http://localhost:8000/api/v1';

function renderSignup() {
  return renderWithProviders(
    <Routes>
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<div>LOGIN_PAGE</div>} />
    </Routes>,
    { routerEntries: ['/signup'] },
  );
}

describe('pages/auth/SignupPage', () => {
  it('renders the form (no PasswordStrengthMeter while password is empty)', () => {
    renderSignup();

    expect(screen.getByLabelText("Nom d'utilisateur", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Mot de passe/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Demander la création du compte/i })).toBeInTheDocument();
    // PasswordStrengthMeter renders nothing when password is empty
    expect(screen.queryByText(/Force du mot de passe/i)).not.toBeInTheDocument();
  });

  it('shows the PasswordStrengthMeter once a password is typed', async () => {
    const user = userEvent.setup();
    renderSignup();

    const pwInput = screen.getByLabelText(/^Mot de passe/i);
    await user.type(pwInput, 'Abc1!xyz');

    expect(await screen.findByText(/Force du mot de passe/i)).toBeInTheDocument();
  });

  it('shows the success toast and navigates to /login after a successful signup', async () => {
    const user = userEvent.setup();
    renderSignup();

    await user.type(screen.getByLabelText("Nom d'utilisateur", { exact: false }), 'newuser');
    await user.type(screen.getByLabelText(/^Mot de passe/i), 'GoodPass1!');
    await user.type(screen.getByLabelText(/Confirmer le mot de passe/i), 'GoodPass1!');
    await user.type(screen.getByLabelText(/Nom de famille/i), 'Doe');
    await user.type(screen.getByLabelText(/Prénom/i), 'John');
    await user.type(screen.getByLabelText(/Adresse e-mail/i), 'john@doe.fr');

    await user.click(screen.getByRole('button', { name: /Demander la création du compte/i }));

    await waitFor(
      () => {
        expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it('renders an ErrorAlert with the AUTH_1023 message when username is taken', async () => {
    server.use(
      http.post(`${BASE_URL}/auth/signup`, () =>
        HttpResponse.json(
          { code: 'AUTH_1023', message: 'Pris' },
          { status: 409 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderSignup();

    await user.type(screen.getByLabelText("Nom d'utilisateur", { exact: false }), 'existing');
    await user.type(screen.getByLabelText(/^Mot de passe/i), 'GoodPass1!');
    await user.type(screen.getByLabelText(/Confirmer le mot de passe/i), 'GoodPass1!');
    await user.type(screen.getByLabelText(/Nom de famille/i), 'Doe');
    await user.type(screen.getByLabelText(/Prénom/i), 'John');
    await user.type(screen.getByLabelText(/Adresse e-mail/i), 'john@doe.fr');

    await user.click(screen.getByRole('button', { name: /Demander la création du compte/i }));

    expect(await screen.findByText(ERROR_MESSAGES.AUTH_1023)).toBeInTheDocument();
    expect(screen.getByText('Création du compte refusée')).toBeInTheDocument();
  });
});

vi.spyOn(console, 'warn').mockImplementation(() => {});
