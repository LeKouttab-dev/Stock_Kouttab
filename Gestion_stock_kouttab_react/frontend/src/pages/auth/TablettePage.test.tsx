import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { server } from '@/test/mocks/server';
import { mockUser } from '@/test/mocks/handlers';
import { renderWithProviders, screen } from '@/test/test-utils';
import { useAuthStore } from '@/stores/auth';
import { USERNAME_TABLETTE, operateurMemorise, quitterModeTablette } from '@/lib/tablette';
import { TablettePage } from './TablettePage';

const BASE_URL = 'http://localhost:8000/api/v1';

const COMPTE = {
  ...mockUser,
  id: 42,
  username: USERNAME_TABLETTE,
  role: 'AdminStock' as const,
  prenom: 'Tablette',
  nom: 'buvette',
  operateur: 'Youssef',
};

function Ici() {
  const location = useLocation();
  return <p data-testid="ici">{location.pathname + location.search}</p>;
}

function rendre() {
  renderWithProviders(
    <Routes>
      <Route path="/tablette" element={<TablettePage />} />
      <Route path="/buvette" element={<Ici />} />
      <Route path="/login" element={<Ici />} />
    </Routes>,
    { routerEntries: ['/tablette'] },
  );
}

beforeEach(() => {
  quitterModeTablette();
});

afterEach(() => {
  window.history.replaceState(null, '', '/');
  quitterModeTablette();
});

describe('pages/auth/TablettePage', () => {
  it("enregistre la session, efface l'ancre et ouvre la buvette en mode tablette", async () => {
    let autorisation: string | null = null;
    server.use(
      http.get(`${BASE_URL}/auth/me`, ({ request }) => {
        autorisation = request.headers.get('Authorization');
        return HttpResponse.json(COMPTE);
      }),
    );
    window.history.replaceState(
      null,
      '',
      '/tablette#access=jeton-acces&refresh=jeton-refresh&op=Youssef%20B.',
    );

    rendre();

    expect(await screen.findByTestId('ici')).toHaveTextContent('/buvette?mode=tablette');
    // L'ancre (les jetons) a quitté la barre d'adresse et l'historique.
    expect(window.location.hash).toBe('');
    expect(window.location.href).not.toContain('jeton-acces');
    expect(autorisation).toBe('Bearer jeton-acces');

    const etat = useAuthStore.getState();
    expect(etat.accessToken).toBe('jeton-acces');
    expect(etat.refreshToken).toBe('jeton-refresh');
    expect(etat.user?.username).toBe(USERNAME_TABLETTE);
    expect(operateurMemorise()).toBe('Youssef B.');
  });

  it("sans jetons dans l'ancre, renvoie vers la connexion", async () => {
    window.history.replaceState(null, '', '/tablette#op=Youssef');

    rendre();

    expect(await screen.findByTestId('ici')).toHaveTextContent('/login');
    expect(window.location.hash).toBe('');
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(operateurMemorise()).toBeNull();
  });
});
