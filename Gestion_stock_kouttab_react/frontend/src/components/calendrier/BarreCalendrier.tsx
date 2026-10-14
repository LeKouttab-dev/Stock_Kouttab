import { ChevronLeft, ChevronRight, Columns3, PanelLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { VueCalendrier } from '@/hooks/useCalendrierVue';

const LIBELLES: Record<VueCalendrier, string> = {
  mois: 'Mois',
  semaine: 'Semaine',
  'trois-jours': '3 jours',
  jour: 'Jour',
  liste: 'Liste',
};

/**
 * Masqué sur téléphone : « Semaine » y sert déjà la liste de la semaine, un
 * bouton « Liste » ferait doublon.
 */
const BUREAU_SEULEMENT: VueCalendrier[] = ['liste'];

interface BarreCalendrierProps {
  vue: VueCalendrier;
  /** La vue choisie, avant adaptation au téléphone : c'est elle qui s'affiche active. */
  choisie?: VueCalendrier;
  titre: string;
  parSalle: boolean;
  panneauOuvert: boolean;
  rafraichissement: boolean;
  onVue: (vue: VueCalendrier) => void;
  onDecaler: (sens: -1 | 1) => void;
  onAujourdhui: () => void;
  onParSalle: () => void;
  onPanneau: () => void;
  onRafraichir?: () => void;
}

export function BarreCalendrier({
  vue,
  choisie = vue,
  titre,
  parSalle,
  panneauOuvert,
  rafraichissement,
  onVue,
  onDecaler,
  onAujourdhui,
  onParSalle,
  onPanneau,
  onRafraichir,
}: BarreCalendrierProps) {
  const grille = vue !== 'mois' && vue !== 'liste';

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-sand-200 bg-cream-50 px-3 py-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-expanded={panneauOuvert}
        aria-controls="panneau-filtres"
        onClick={onPanneau}
      >
        <PanelLeft className="h-4 w-4" />
        <span className="sr-only sm:not-sr-only">Filtres</span>
      </Button>

      <div className="flex items-center">
        <Button type="button" variant="ghost" size="sm" aria-label="Précédent" onClick={() => onDecaler(-1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onAujourdhui}>
          Aujourd&apos;hui
        </Button>
        <Button type="button" variant="ghost" size="sm" aria-label="Suivant" onClick={() => onDecaler(1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <h1 className="font-serif text-base font-bold text-forest sm:text-lg">{titre}</h1>

      <div className="ml-auto flex flex-wrap items-center gap-1">
        {grille && (
          <Button
            type="button"
            variant={parSalle ? 'primary' : 'outline'}
            size="sm"
            aria-pressed={parSalle}
            onClick={onParSalle}
          >
            <Columns3 className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only">Par salle</span>
          </Button>
        )}

        <div className="flex rounded-md border border-sand-200">
          {(Object.keys(LIBELLES) as VueCalendrier[]).map((cle) => (
            <button
              key={cle}
              type="button"
              aria-pressed={choisie === cle}
              onClick={() => onVue(cle)}
              className={cn(
                'px-2 py-1 text-xs first:rounded-l-md last:rounded-r-md',
                BUREAU_SEULEMENT.includes(cle) && 'hidden lg:inline-block',
                choisie === cle ? 'bg-forest text-cream-100' : 'text-forest hover:bg-cream-100',
              )}
            >
              {LIBELLES[cle]}
            </button>
          ))}
        </div>

        {onRafraichir && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Rafraîchir"
            disabled={rafraichissement}
            onClick={onRafraichir}
          >
            <RefreshCw className={cn('h-4 w-4', rafraichissement && 'animate-spin')} />
          </Button>
        )}
      </div>
    </div>
  );
}
