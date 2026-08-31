import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DocumentScanner } from '../DocumentScanner';

/**
 * Le bouton « Valider » tournait dans le vide.
 *
 * `preparerCadrage` dépendait de l'objet rendu par `useMutation`, qui change
 * d'identité à CHAQUE changement d'état, `isPending` compris. Lancer la
 * détection recréait donc la fonction, ce qui relançait l'effet du fichier
 * déposé, qui relançait la détection : une boucle infinie. Le serveur était
 * noyé de requêtes — d'où des poignées très lentes à venir — et `isPending` ne
 * retombait jamais, donc le bouton restait bloqué en chargement.
 *
 * La dépendance porte maintenant sur `detect.mutate`, qui est stable, et un
 * `useRef` retient le fichier déjà préparé.
 */

const detectMutate = vi.fn();

vi.mock('@/api/endpoints/scan', () => ({
  useDetectDocument: () => ({ mutate: detectMutate, isPending: false }),
  useApplyScan: () => ({ mutate: vi.fn(), isPending: false }),
}));

// jsdom ne décode aucune image : on rend un bitmap crédible.
beforeEach(() => {
  detectMutate.mockClear();
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width: 1200, height: 1600, close: vi.fn() })),
  );
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() })) as never;
  HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
    cb(new Blob(['x'], { type: 'image/jpeg' }));
  } as never;
  URL.createObjectURL = vi.fn(() => 'blob:apercu');
  URL.revokeObjectURL = vi.fn();
});

function afficher(fichier: File) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DocumentScanner open fichierInitial={fichier} onClose={vi.fn()} onScanned={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('components/scanner/DocumentScanner — fichier déposé', () => {
  it('ne lance la détection qu’une seule fois', async () => {
    afficher(new File(['x'], 'ticket.jpg', { type: 'image/jpeg' }));

    await waitFor(() => expect(detectMutate).toHaveBeenCalledTimes(1));

    // Laisser passer plusieurs rendus : la boucle se manifestait au deuxième.
    await new Promise((r) => setTimeout(r, 80));
    expect(detectMutate).toHaveBeenCalledTimes(1);
  });

  it('affiche le cadrage sans attendre la réponse du serveur', async () => {
    /* La détection porte sur plusieurs mégapixels et prend une à deux
       secondes ; l'écran restait vide, sans la moindre poignée à saisir. */
    afficher(new File(['x'], 'ticket.jpg', { type: 'image/jpeg' }));

    // Le mock ne rappelle jamais `onSuccess` : tout ce qui s'affiche vient donc
    // du cadre de repli, posé avant l'aller-retour.
    await waitFor(() => expect(screen.getByText(/recadrer le justificatif/i)).toBeInTheDocument());
    await waitFor(() => expect(document.querySelectorAll('polygon').length).toBeGreaterThan(0));
  });
});
