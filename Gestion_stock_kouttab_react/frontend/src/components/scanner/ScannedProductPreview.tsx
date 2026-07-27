import type { ReactNode } from 'react';
import { fr } from '@/lib/i18n/fr';
import type { BarcodeLookupResponse } from '@/types/api';

/**
 * Blocs d'affichage partagés par les modales de création après scan
 * (inventaire et buvette).
 *
 * Seule la présentation est mutualisée. Les champs des deux formulaires
 * diffèrent réellement — catégorie et seuil d'un côté, prix de l'autre — et les
 * fusionner produirait un composant à options plus difficile à lire que les
 * deux écrans réunis.
 */

export function ScannedBarcodeLine({ barcode }: { barcode: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">{fr.scanner.barcode} :</span>
      <span className="rounded bg-muted px-2 py-1 font-mono text-sm">{barcode}</span>
    </div>
  );
}

interface ScannedProductRowProps {
  lookup: BarcodeLookupResponse;
  /** Champ « nom », dont l'identifiant diffère selon le formulaire. */
  children: ReactNode;
}

/** Vignette OpenFoodFacts (si disponible) accolée au champ du nom. */
export function ScannedProductRow({ lookup, children }: ScannedProductRowProps) {
  const imageUrl = lookup.openfoodfacts?.image_url;
  return (
    <div className="flex gap-3">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={lookup.openfoodfacts?.name ?? 'Produit'}
          className="h-20 w-20 flex-shrink-0 rounded-md border border-border object-cover"
        />
      ) : null}
      <div className="flex-1 space-y-1.5">{children}</div>
    </div>
  );
}
