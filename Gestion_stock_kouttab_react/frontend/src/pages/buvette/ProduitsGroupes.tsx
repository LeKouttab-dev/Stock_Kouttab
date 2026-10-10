import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { BuvetteProductCard } from '@/components/buvette/BuvetteProductCard';
import { GROUPES_PRODUITS, grouperProduits, type GroupeProduits } from '@/lib/buvette';
import { fr } from '@/lib/i18n/fr';
import { cn } from '@/lib/utils';
import type { BuvetteProduct } from '@/types/api';

/** Groupes repliés, mémorisés dans ce navigateur (de simple confort). */
const CLE_STOCKAGE = 'buvette.produits.groupesReplies';

function lireReplies(): Set<GroupeProduits> {
  try {
    const brut = window.localStorage.getItem(CLE_STOCKAGE);
    const liste: unknown = brut ? JSON.parse(brut) : [];
    if (!Array.isArray(liste)) return new Set();
    return new Set(
      liste.filter((g): g is GroupeProduits =>
        (GROUPES_PRODUITS as readonly string[]).includes(String(g)),
      ),
    );
  } catch {
    return new Set();
  }
}

function ecrireReplies(replies: Set<GroupeProduits>): void {
  try {
    window.localStorage.setItem(CLE_STOCKAGE, JSON.stringify([...replies]));
  } catch {
    // Stockage indisponible (navigation privée, quota) : l'état reste en mémoire.
  }
}

interface Props {
  produits: BuvetteProduct[];
  /** Une recherche est en cours : tous les groupes restants sont ouverts. */
  rechercheActive: boolean;
  canEdit: boolean;
  onModifier: (p: BuvetteProduct) => void;
  onDelete: (p: BuvetteProduct) => void;
  onToggleActive: (p: BuvetteProduct) => void;
  onReappro: (p: BuvetteProduct) => void;
}

/**
 * Produits rangés par onglet de la tablette (Sucré-salé, Boissons, Café,
 * Épicerie) puis « Hors tablette », en sections dépliables avec leur compteur.
 */
export function ProduitsGroupes({ produits, rechercheActive, ...actions }: Props) {
  const [replies, setReplies] = useState<Set<GroupeProduits>>(lireReplies);
  const titres = fr.buvette.groupes;

  const basculer = (groupe: GroupeProduits) =>
    setReplies((prec) => {
      const suivant = new Set(prec);
      if (suivant.has(groupe)) suivant.delete(groupe);
      else suivant.add(groupe);
      ecrireReplies(suivant);
      return suivant;
    });

  return (
    <div className="space-y-4">
      {grouperProduits(produits).map(({ groupe, produits: dansLeGroupe }) => {
        const ouvert = rechercheActive || !replies.has(groupe);
        const idContenu = `groupe-produits-${groupe}`;
        return (
          <section key={groupe} aria-label={titres[groupe]} data-testid={`groupe-${groupe}`}>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-left font-serif text-base font-semibold text-forest hover:bg-muted/50"
              aria-expanded={ouvert}
              aria-controls={idContenu}
              disabled={rechercheActive}
              onClick={() => basculer(groupe)}
            >
              <ChevronDown
                className={cn('h-4 w-4 shrink-0 transition-transform', !ouvert && '-rotate-90')}
                aria-hidden
              />
              {`${titres[groupe]} (${dansLeGroupe.length})`}
            </button>
            {ouvert && (
              <div
                id={idContenu}
                className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
              >
                {dansLeGroupe.map((p) => (
                  <BuvetteProductCard key={p.id} product={p} {...actions} />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
