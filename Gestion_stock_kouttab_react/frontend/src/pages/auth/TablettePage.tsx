import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { useAuthStore } from '@/stores/auth';
import { activerModeTablette, lireFragmentTablette, quitterModeTablette } from '@/lib/tablette';
import type { User } from '@/types/api';

/**
 * Porte d'entrée de la tablette de caisse (écran Personnel).
 *
 * La tablette ouvre `/tablette#access=…&refresh=…&op=…` avec une session
 * obtenue par `POST /auth/caisse/session`. On efface l'ancre de l'historique
 * AVANT tout appel (les jetons n'ont pas à y traîner), on enregistre la
 * session comme une connexion normale, puis on file vers la buvette en mode
 * tablette.
 */
export function TablettePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [erreur, setErreur] = useState<unknown>(null);
  // StrictMode rejoue les effets en développement : l'ancre est déjà effacée
  // au second passage, qui renverrait à tort vers la connexion.
  const dejaLance = useRef(false);

  useEffect(() => {
    if (dejaLance.current) return;
    dejaLance.current = true;

    const fragment = lireFragmentTablette(window.location.hash);
    window.history.replaceState(null, '', window.location.pathname);
    if (!fragment) {
      navigate('/login', { replace: true });
      return;
    }

    // Rien de la session précédente (données en cache, mode) ne doit subsister.
    queryClient.clear();
    quitterModeTablette();
    const store = useAuthStore.getState();
    store.logout();
    store.setTokens({ accessToken: fragment.access, refreshToken: fragment.refresh });

    api
      .get<User>('/auth/me')
      .then(({ data }) => {
        // Le refresh a pu tourner pendant l'appel : relire les jetons courants.
        const { accessToken, refreshToken } = useAuthStore.getState();
        useAuthStore.getState().setSession({
          user: data,
          accessToken: accessToken ?? fragment.access,
          refreshToken: refreshToken ?? fragment.refresh,
        });
        activerModeTablette(fragment.op ?? data.operateur ?? data.prenom);
        navigate('/buvette?mode=tablette', { replace: true });
      })
      .catch((err: unknown) => {
        useAuthStore.getState().logout();
        setErreur(err);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        {erreur ? (
          <ErrorAlert
            error={erreur}
            title="Session de la tablette refusée"
            fallback="Revenez à l'écran Personnel de la tablette et saisissez de nouveau votre nom."
          />
        ) : (
          <LoadingSpinner label="Ouverture de la buvette…" />
        )}
      </div>
    </div>
  );
}
