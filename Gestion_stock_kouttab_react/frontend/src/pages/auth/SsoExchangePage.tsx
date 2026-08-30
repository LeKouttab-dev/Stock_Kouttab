import { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { Logo } from '@/components/shared/Logo';
import { useSsoExchange } from '@/api/endpoints/auth';
import { jetonDepuisFragment } from '@/lib/sso';
import { pageParDefaut } from '@/lib/auth';

/**
 * Porte d'entrée du passage signé depuis gestion.lekouttab.fr.
 *
 * L'outil de gestion ouvre `/sso#jeton=…` ; cette page échange le jeton
 * contre une session puis file vers la page par défaut du rôle — les notes de
 * frais pour un compte « BenevoleFrais ». Le fragment est effacé de la barre
 * d'adresse avant l'échange : un jeton, même consommé, n'a pas à traîner dans
 * l'historique du navigateur.
 */
export function SsoExchangePage() {
  const navigate = useNavigate();
  const exchange = useSsoExchange();
  // Le jeton est à usage unique et StrictMode rejoue les effets en
  // développement : sans ce verrou, le second passage consommerait un jeton
  // déjà brûlé et afficherait une erreur fantôme.
  const dejaLance = useRef(false);

  useEffect(() => {
    if (dejaLance.current) return;
    dejaLance.current = true;

    const jeton = jetonDepuisFragment(window.location.hash);
    window.history.replaceState(null, '', window.location.pathname);
    if (!jeton) {
      navigate('/login', { replace: true });
      return;
    }
    exchange
      .mutateAsync({ token: jeton })
      .then((data) => navigate(pageParDefaut(data.user.role), { replace: true }))
      .catch(() => {
        /* rendu ci-dessous */
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const erreur = exchange.isError ? exchange.error : null;

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-md border-border bg-card shadow-xl">
        <CardHeader className="space-y-2 text-center">
          <Logo className="mx-auto h-16 w-16 rounded-full shadow-md" />
          <CardTitle className="font-serif text-2xl text-forest">Le Kouttâb — Stock</CardTitle>
          <CardDescription>Connexion depuis l&apos;outil de gestion…</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {erreur ? (
            <>
              <ErrorAlert
                error={erreur}
                title="Le passage n'a pas abouti"
                fallback="Le lien a expiré ou a déjà servi. Retournez sur l'outil de gestion et cliquez à nouveau sur « Notes de frais »."
              />
              <p className="text-center text-sm text-muted-foreground">
                <Link className="underline" to="/login">
                  Se connecter avec un compte Gestion Stock
                </Link>
              </p>
            </>
          ) : (
            <LoadingSpinner label="Ouverture de votre session…" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
