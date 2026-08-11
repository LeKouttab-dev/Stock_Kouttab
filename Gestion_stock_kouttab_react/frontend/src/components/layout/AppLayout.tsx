import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
