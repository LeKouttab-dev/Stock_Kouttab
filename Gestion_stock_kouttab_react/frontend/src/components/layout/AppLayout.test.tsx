import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { act } from '@testing-library/react';
import { server } from '@/test/mocks/server';
import { mockUser } from '@/test/mocks/handlers';
import { renderWithProviders, screen } from '@/test/test-utils';
import { useAuthStore } from '@/stores/auth';
import { USERNAME_TABLETTE, activerModeTablette, quitterModeTablette } from '@/lib/tablette';
import type { PendingSummary } from '@/types/api';
import { AppLayout } from './AppLayout';

const BASE_URL = 'http://localhost:8000/api/v1';

const RIEN: PendingSummary = {
  notes_a_valider: 0,
  factures_a_traiter: 0,
  modifications_stock: 0,
  comptes_a_valider: 0,
  articles_en_alerte: 0,
  justificatifs_demandes: 0,
  tickets_ouverts: 0,
  notes_suivies: 0,
  factures_suivies: 0,
  conversations_a_traiter: 0,
  conversations_non_lues: 0,
};

function Ici() {
  const location = useLocation();
  return <p data-testid="ici">{location.pathname + location.search}</p>;
}

function rendre(adresse: string) {
  return renderWithProviders(
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/buvette" element={<Ici />} />
        <Route path="/profile" element={<Ici />} />
      </Route>
    </Routes>,
    { routerEntries: [adresse] },
  );
}

function connecterTablette() {
  act(() => {
    useAuthStore.setState({
      user: { ...mockUser, role: 'AdminStock', username: USERNAME_TABLETTE },
      accessToken: 'jeton',
      refreshToken: 'rafraichir',
    });
  });
}

// Le rendu part d'un store vide (coquille standard) avant la connexion.
beforeEach(() => {
  server.use(http.get(`${BASE_URL}/notifications/summary`, () => HttpResponse.json(RIEN)));
});

afterEach(() => {
  quitterModeTablette();
  document.documentElement.classList.remove('mode-tablette');
});

describe('components/layout/AppLayout : mode tablette', () => {
  it('sans menu latéral ni barre du haut, avec le bandeau du nom', async () => {
    activerModeTablette('Youssef');
    rendre('/buvette?mode=tablette');
    connecterTablette();

    expect(await screen.findByRole('status')).toHaveTextContent('Connecté : Youssef (tablette)');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Menu utilisateur' })).not.toBeInTheDocument();
    expect(screen.queryByText(/Déconnexion/i)).not.toBeInTheDocument();
    expect(document.documentElement).toHaveClass('mode-tablette');
  });

  it('ramène toute autre page vers la buvette', async () => {
    activerModeTablette('Youssef');
    rendre('/profile');
    connecterTablette();

    expect(await screen.findByTestId('ici')).toHaveTextContent('/buvette?mode=tablette');
  });

  it('une connexion ordinaire garde la coquille complète', async () => {
    // Un reste de mode tablette ne suffit pas : c'est le compte qui décide.
    activerModeTablette('Youssef');
    rendre('/buvette');
    act(() => {
      useAuthStore.setState({
        user: { ...mockUser, role: 'AdminStock' },
        accessToken: 'jeton',
        refreshToken: 'rafraichir',
      });
    });

    expect(await screen.findByRole('button', { name: 'Menu utilisateur' })).toBeInTheDocument();
    expect(screen.queryByText(/\(tablette\)/)).not.toBeInTheDocument();
    expect(document.documentElement).not.toHaveClass('mode-tablette');
  });
});
