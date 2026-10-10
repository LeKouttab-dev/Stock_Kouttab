import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useRappelConnexion } from '@/hooks/useRappelConnexion';
import { useModeTablette } from '@/hooks/useModeTablette';

export function AppLayout() {
  const { actif: tablette } = useModeTablette();
  return tablette ? <CoquilleTablette /> : <CoquilleStandard />;
}

function CoquilleStandard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto overscroll-contain px-4 py-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
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
    <div className="mode-tablette flex h-dvh flex-col overflow-hidden bg-background text-foreground">
      <div
        role="status"
        className="shrink-0 border-b border-border bg-card/90 px-4 py-1.5 text-sm text-muted-foreground"
      >
        Connecté : <span className="font-medium text-forest">{operateur ?? 'Tablette'}</span>{' '}
        (tablette)
      </div>
      <main className="flex-1 overflow-y-auto overscroll-contain px-4 py-4">
        <div className="mx-auto w-full max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
