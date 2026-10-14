import { useMemo } from 'react';
import {
  MINUTE_DEBUT,
  MINUTE_FIN,
  PX_PAR_MINUTE,
  colonneDe,
  disposer,
  fusionnerMicroCreneaux,
  minutesParis,
  placer,
  type BlocGrille,
  type Disposition,
} from '@/lib/calendrier-grille';
import { cn } from '@/lib/utils';
import type { EvenementCalendrier } from '@/types/api';
import { CarteSeance } from './CarteSeance';

// Juste ce qu'il faut pour « 15 » : la première version gardait 3,25 rem pour
// « 15 h », et chaque pixel pris ici manque à une colonne de salle.
const LARGEUR_GOUTTIERE = '2rem';
const HAUTEUR_TOTALE = (MINUTE_FIN - MINUTE_DEBUT) * PX_PAR_MINUTE;

/** Clé de la colonne d'un jour sans aucun cours. */
const JOUR_VIDE = '__vide__';
const TOUTES = '__toutes__';

const JOUR_COURT = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Paris',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
});

/**
 * La séparation entre deux jours : un trait sombre et épais, comme dans Google
 * Agenda. Entre les salles d'une même journée, le trait reste clair.
 *
 * Sans cette hiérarchie, douze colonnes de la même couleur se lisent comme
 * douze jours : on ne sait plus où finit le mercredi.
 */
function bordure(indexJour: number, nombreJours: number, derniereDuJour: boolean): string {
  if (!derniereDuJour) return 'border-r border-r-sand-200';
  return indexJour === nombreJours - 1
    ? 'border-r border-r-sand-200'
    : 'border-r-2 border-r-forest-600';
}

interface GrilleSallesProps {
  jours: string[];
  evenements: EvenementCalendrier[];
  salles: Record<string, string>;
  /** Clés de salle autorisées par le filtre, dans l'ordre du référentiel. */
  sallesVisibles: string[];
  parSalle: boolean;
  maintenant: { jour: string; minutes: number } | null;
  onOuvrir: (bloc: BlocGrille) => void;
}

/**
 * L'emploi du temps : une colonne par (jour × salle occupée), les heures en
 * ordonnée.
 *
 * **Un seul conteneur défile.** Les en-têtes et la gouttière des heures sont
 * `sticky` à l'intérieur de ce conteneur unique, et non des blocs séparés dont
 * il faudrait recopier le défilement en JavaScript. C'est ce qui garde les
 * deux axes alignés par construction. L'invariant « un seul élément défile »
 * de `AppLayout` n'est pas levé pour autant : il descend d'un niveau.
 *
 * **Une salle sans cours ce jour-là n'a pas de colonne.** Une colonne vide ne
 * dit rien qu'on ne lise déjà par son absence, et elle prend la place d'une
 * colonne pleine. L'ordre des salles reste celui du référentiel, pour qu'une
 * salle soit toujours au même rang d'un jour à l'autre quand elle est là.
 *
 * Les lignes d'heures sont un dégradé répété, pas des centaines de `<div>` :
 * sa période est calculée depuis la même constante que les cartes, les deux
 * ne peuvent donc pas dériver.
 */
export function GrilleSalles({
  jours,
  evenements,
  salles,
  sallesVisibles,
  parSalle,
  maintenant,
  onOuvrir,
}: GrilleSallesProps) {
  /** Les événements de la vue, rangés par jour puis par colonne. */
  const paniers = useMemo(() => {
    const resultat = new Map<string, Map<string, EvenementCalendrier[]>>();
    for (const evenement of evenements) {
      const jour = minutesParis(evenement.debut).jour;
      if (!jours.includes(jour)) continue;
      const colonne = parSalle ? colonneDe(evenement, salles) : TOUTES;
      if (parSalle && !sallesVisibles.includes(colonne)) continue;
      const duJour = resultat.get(jour) ?? new Map<string, EvenementCalendrier[]>();
      duJour.set(colonne, [...(duJour.get(colonne) ?? []), evenement]);
      resultat.set(jour, duJour);
    }
    return resultat;
  }, [evenements, jours, salles, sallesVisibles, parSalle]);

  /**
   * Les colonnes de chaque jour : les salles occupées, dans l'ordre du
   * référentiel. Un jour sans aucun cours garde une colonne étroite — sinon il
   * disparaîtrait de la semaine, et on ne saurait plus si c'est un jour vide
   * ou un jour manquant.
   */
  const colonnesParJour = useMemo(() => {
    const resultat = new Map<string, string[]>();
    for (const jour of jours) {
      const duJour = paniers.get(jour);
      let colonnes: string[];
      if (!parSalle) colonnes = [TOUTES];
      else colonnes = sallesVisibles.filter((cle) => (duJour?.get(cle)?.length ?? 0) > 0);
      resultat.set(jour, colonnes.length ? colonnes : [JOUR_VIDE]);
    }
    return resultat;
  }, [jours, paniers, parSalle, sallesVisibles]);

  /** La disposition de chaque colonne : le long dessous, le court par-dessus. */
  const dispositions = useMemo(() => {
    const resultat = new Map<string, Disposition[]>();
    for (const [jour, duJour] of paniers) {
      for (const [colonne, liste] of duJour) {
        resultat.set(`${jour}::${colonne}`, disposer(fusionnerMicroCreneaux(liste)));
      }
    }
    return resultat;
  }, [paniers]);

  /** Ce qui ne tient pas dans 08:00–22:30, par jour. Rien ne doit disparaître. */
  const horsPlage = useMemo(() => {
    const resultat = new Map<string, EvenementCalendrier[]>();
    for (const evenement of evenements) {
      const debut = minutesParis(evenement.debut);
      const fin = minutesParis(evenement.fin);
      if (!jours.includes(debut.jour)) continue;
      const finMinutes = fin.jour === debut.jour ? fin.minutes : MINUTE_FIN;
      if (placer(debut.minutes, finMinutes) === null) {
        resultat.set(debut.jour, [...(resultat.get(debut.jour) ?? []), evenement]);
      }
    }
    return resultat;
  }, [evenements, jours]);

  const heures: number[] = [];
  for (let m = Math.ceil(MINUTE_DEBUT / 60) * 60; m <= MINUTE_FIN; m += 60) heures.push(m);

  const gabarit = [
    LARGEUR_GOUTTIERE,
    ...jours.flatMap((jour) =>
      (colonnesParJour.get(jour) ?? []).map((colonne) =>
        colonne === JOUR_VIDE ? 'minmax(3rem, 0.4fr)' : 'minmax(6.5rem, 1fr)',
      ),
    ),
  ].join(' ');

  const libelle = (colonne: string) =>
    colonne === TOUTES ? 'Tous les agendas' : colonne === JOUR_VIDE ? '' : (salles[colonne] ?? colonne);

  return (
    <div className="emploi-du-temps relative min-h-0 flex-1 overflow-auto">
      {/* Pas de `min-w-max` : il figerait les colonnes à leur largeur
          minimale et tronquerait les noms alors que la place est là. Le
          `minmax()` suffit — les colonnes s'étirent pour remplir, et ne
          débordent (avec défilement horizontal) qu'une fois le plancher
          atteint. */}
      <div
        className="grid"
        style={
          {
            gridTemplateColumns: gabarit,
            // Lu par `.lignes-horaires` : le fond et les cartes tiennent leur
            // échelle de la même constante.
            '--px-par-minute': PX_PAR_MINUTE,
          } as React.CSSProperties
        }
      >
        {/* Les deux rangées d'en-tête sont collées l'une à l'autre AU PIXEL :
            la rangée des jours mesure exactement `h-7`, et celle des salles se
            colle à `top-7`. Une fente entre les deux laissait voir les cours
            qui défilaient dessous. */}
        <div className="sticky left-0 top-0 z-30 h-7 border-b border-r border-sand-200 bg-cream-50" />

        {jours.map((jour, i) => (
          <div
            key={`jour-${jour}`}
            style={{ gridColumn: `span ${colonnesParJour.get(jour)?.length ?? 1}` }}
            className={cn(
              'sticky top-0 z-20 flex h-7 items-center justify-center truncate border-b bg-cream-50 px-1 text-xs font-semibold text-forest',
              bordure(i, jours.length, true),
              jour === maintenant?.jour && 'bg-terracotta-50',
            )}
          >
            {JOUR_COURT.format(new Date(`${jour}T12:00:00`))}
            {horsPlage.has(jour) && (
              <span className="ml-1 font-normal text-terracotta" title="Hors de la plage affichée">
                +{horsPlage.get(jour)?.length} hors plage
              </span>
            )}
          </div>
        ))}

        {/* Deuxième rangée d'en-tête : les salles, sous chaque jour. */}
        <div className="sticky left-0 top-7 z-30 border-b border-r border-sand-300 bg-cream-50 shadow-sm" />
        {jours.map((jour, i) => {
          const colonnes = colonnesParJour.get(jour) ?? [];
          return colonnes.map((colonne, j) => (
            <div
              key={`salle-${jour}-${colonne}`}
              className={cn(
                'sticky top-7 z-20 truncate border-b border-sand-300 bg-cream-50 px-1 py-0.5 text-center text-[11px] text-forest/70 shadow-sm',
                bordure(i, jours.length, j === colonnes.length - 1),
              )}
            >
              {libelle(colonne) || ' '}
            </div>
          ));
        })}

        {/* La gouttière des heures, collée à gauche. */}
        <div
          className="sticky left-0 z-10 border-r border-sand-200 bg-cream-50"
          style={{ height: HAUTEUR_TOTALE }}
        >
          {heures.map((minute) => (
            <span
              key={minute}
              className="absolute right-0.5 -translate-y-1/2 text-[10px] tabular-nums text-forest/50"
              style={{ top: (minute - MINUTE_DEBUT) * PX_PAR_MINUTE }}
            >
              {Math.floor(minute / 60)}
            </span>
          ))}
        </div>

        {jours.map((jour, i) => {
          const colonnes = colonnesParJour.get(jour) ?? [];
          return colonnes.map((colonne, j) => {
            const places = dispositions.get(`${jour}::${colonne}`) ?? [];
            return (
              <section
                key={`col-${jour}-${colonne}`}
                aria-label={`${JOUR_COURT.format(new Date(`${jour}T12:00:00`))} — ${
                  libelle(colonne) || 'aucun cours'
                }`}
                // `z-0` isole la colonne : ses cartes, posées en absolu, ne
                // peuvent plus passer par-dessus les en-têtes collants.
                className={cn(
                  'lignes-horaires relative z-0',
                  bordure(i, jours.length, j === colonnes.length - 1),
                )}
                style={{ height: HAUTEUR_TOTALE }}
              >
                {/* Les cartes sont posées en absolu : l'ordre du DOM ne suit
                    l'ordre visuel que si on le force. Il est chronologique,
                    pour que la tabulation parcoure la journée dans l'ordre. */}
                {places.map(({ bloc, gauche, largeur, plan }) => {
                  const position = placer(bloc.debutMinutes, bloc.finMinutes);
                  if (!position) return null;
                  return (
                    <div
                      key={bloc.cle}
                      className="absolute px-px"
                      style={{
                        top: position.top,
                        left: `${gauche}%`,
                        width: `${largeur}%`,
                        zIndex: plan,
                      }}
                    >
                      <CarteSeance
                        bloc={bloc}
                        hauteur={position.hauteur}
                        largeur={largeur}
                        posee={plan > 1}
                        onOuvrir={onOuvrir}
                      />
                    </div>
                  );
                })}

                {jour === maintenant?.jour &&
                  maintenant.minutes >= MINUTE_DEBUT &&
                  maintenant.minutes <= MINUTE_FIN && (
                    <div
                      aria-hidden
                      className="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-terracotta-500"
                      style={{ top: (maintenant.minutes - MINUTE_DEBUT) * PX_PAR_MINUTE }}
                    />
                  )}
              </section>
            );
          });
        })}
      </div>
    </div>
  );
}
