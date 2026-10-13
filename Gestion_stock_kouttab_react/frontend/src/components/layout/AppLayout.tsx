import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useRappelConnexion } from '@/hooks/useRappelConnexion';
import { useModeTablette } from '@/hooks/useModeTablette';
import { useSidebarRepliee } from '@/hooks/useSidebarRepliee';
import { estPleineLargeur } from '@/lib/layout';

export function AppLayout() {
  const { actif: tablette } = useModeTablette();
  return tablette ? <CoquilleTablette /> : <CoquilleStandard />;
}

function CoquilleStandard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  const pleine = estPleineLargeur(pathname);
  const { repliee, basculer } = useSidebarRepliee(pathname);
  // Rappel de ce qui attend l'utilisateur, une fois par connexion. Place ici
  // parce que toute page authentifiee passe par cette coquille.
  useRappelConnexion();

  return (
    // `h-dvh` + `overflow-hidden` : la coquille occupe exactement la hauteur de
    // l'écran et ne peut pas grandir. Un seul élément défile, `<main>`.
    //
    // Avant, `min-h-screen` laissait ce conteneur dépasser la fenêtre : le
    // document défilait DE PLUS que le contenu interne. Arrivé en bas du
    // premier défilement, un second prenait le relais et décalait toute
    // l'interface — barre latérale et barre du haut comprises.
    //
    // `dvh` et non `vh` : sur mobile, `100vh` ignore la barre d'adresse et vaut
    // plus que la surface réellement visible, ce qui rognait le bas de page.
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} repliee={repliee} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar
          onMenuClick={() => setSidebarOpen(true)}
          sidebarRepliee={repliee}
          onBasculerSidebar={basculer}
        />
        {/* L'invariant « un seul élément défile » tient toujours en pleine
            largeur — il DESCEND simplement d'un niveau. Ici `<main>` ne
            défile plus ; c'est la page qui porte sa propre zone de
            défilement, et il n'y en a toujours qu'une. */}
        <main
          className={
            pleine
              ? 'flex min-h-0 flex-1 flex-col overflow-hidden'
              : 'flex-1 overflow-y-auto overscroll-contain px-4 py-6 lg:px-8'
          }
        >
          {pleine ? (
            <Outlet />
          ) : (
            <div className="mx-auto w-full max-w-7xl">
              <Outlet />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/**
 * Mode tablette (écran Personnel de la tablette de caisse) : ni menu latéral,
 * ni barre du haut, ni déconnexion — c'est la tablette qui gère la sortie.
 * Buvette seule : toute autre adresse y ramène. Cibles tactiles agrandies
 * (classe `mode-tablette`, cf. `index.css`).
 */
function CoquilleTablette() {
  const { operateur } = useModeTablette();
  const location = useLocation();

  // Sur <html> aussi : les fenêtres (Radix) sont rendues hors de la coquille,
  // dans un portail, et doivent garder des cibles tactiles agrandies.
  useEffect(() => {
    document.documentElement.classList.add('mode-tablette');
    return () => document.documentElement.classList.remove('mode-tablette');
  }, []);

  if (location.pathname !== '/buvette') {
    return <Navigate to="/buvette?mode=tablette" replace />;
  }

  return (
    // Hauteur portee par le contenu, defilement par la page : jamais `h-dvh`
    // + `overflow-hidden`. Dans la WebView de la tablette (0.8.4, WebView en
    // WRAP_CONTENT), la hauteur du viewport valait 0 et rognait toute la page.
    <div className="mode-tablette flex min-h-dvh flex-col bg-background text-foreground">
      <div
        role="status"
        className="sticky top-0 z-10 shrink-0 border-b border-border bg-card/90 px-4 py-1.5 text-sm text-muted-foreground"
      >
        Connecté : <span className="font-medium text-forest">{operateur ?? 'Tablette'}</span>{' '}
        (tablette)
      </div>
      <main className="flex-1 px-4 py-4">
        <div className="mx-auto w-full max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
