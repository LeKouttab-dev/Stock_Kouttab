import { useMemo } from 'react';
import {
  MINUTE_DEBUT,
  MINUTE_FIN,
  PX_PAR_MINUTE,
  colonneDe,
  fusionnerMicroCreneaux,
  minutesParis,
  placer,
  repartirEnVoies,
  type BlocGrille,
} from '@/lib/calendrier-grille';
import { cn } from '@/lib/utils';
import type { EvenementCalendrier } from '@/types/api';
import { CarteSeance } from './CarteSeance';

const LARGEUR_GOUTTIERE = '3.25rem';
const HAUTEUR_TOTALE = (MINUTE_FIN - MINUTE_DEBUT) * PX_PAR_MINUTE;

const JOUR_COURT = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Paris',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
});

interface GrilleSallesProps {
  jours: string[];
  evenements: EvenementCalendrier[];
  salles: Record<string, string>;
  /** Clés de salle affichées, dans l'ordre. Vide = pas de découpage par salle. */
  sallesVisibles: string[];
  parSalle: boolean;
  maintenant: { jour: string; minutes: number } | null;
  onOuvrir: (bloc: BlocGrille) => void;
}

/**
 * L'emploi du temps : une colonne par (jour × salle), les heures en ordonnée.
 *
 * **Un seul conteneur défile.** Les en-têtes et la gouttière des heures sont
 * `sticky` à l'intérieur de ce conteneur unique, et non des blocs séparés dont
 * il faudrait recopier le défilement en JavaScript. C'est ce qui garde les
 * deux axes alignés par construction — et c'est l'argument décisif contre
 * l'idée de juxtaposer une instance de calendrier par salle, qui donnerait
 * autant de zones de défilement indépendantes.
 *
 * L'invariant « un seul élément défile » de `AppLayout` n'est pas levé pour
 * autant : il descend d'un niveau, du `<main>` jusqu'ici.
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
  // Mémorisé : un nouveau tableau à chaque rendu annulerait le regroupement
  // ci-dessous, qui est le calcul le plus lourd de l'écran.
  const colonnes = useMemo(
    () => (parSalle ? sallesVisibles : ['toutes']),
    [parSalle, sallesVisibles],
  );

  /** Les blocs rangés par colonne, chacun avec sa voie. */
  const parColonne = useMemo(() => {
    const paniers = new Map<string, EvenementCalendrier[]>();
    for (const evenement of evenements) {
      const jour = minutesParis(evenement.debut).jour;
      if (!jours.includes(jour)) continue;
      const colonne = parSalle ? colonneDe(evenement, salles) : 'toutes';
      if (parSalle && !colonnes.includes(colonne)) continue;
      const cle = `${jour}::${colonne}`;
      paniers.set(cle, [...(paniers.get(cle) ?? []), evenement]);
    }
    const resultat = new Map<string, ReturnType<typeof repartirEnVoies>>();
    for (const [cle, liste] of paniers) {
      resultat.set(cle, repartirEnVoies(fusionnerMicroCreneaux(liste)));
    }
    return resultat;
  }, [evenements, jours, salles, parSalle, colonnes]);

  /** Ce qui ne tient pas dans 08:00–22:30, par jour. Rien ne doit disparaître. */
  const horsPlage = useMemo(() => {
    const paniers = new Map<string, EvenementCalendrier[]>();
    for (const evenement of evenements) {
      const debut = minutesParis(evenement.debut);
      const fin = minutesParis(evenement.fin);
      if (!jours.includes(debut.jour)) continue;
      const finMinutes = fin.jour === debut.jour ? fin.minutes : MINUTE_FIN;
      if (placer(debut.minutes, finMinutes) === null) {
        paniers.set(debut.jour, [...(paniers.get(debut.jour) ?? []), evenement]);
      }
    }
    return paniers;
  }, [evenements, jours]);

  const heures: number[] = [];
  for (let m = Math.ceil(MINUTE_DEBUT / 60) * 60; m <= MINUTE_FIN; m += 60) heures.push(m);

  const gabarit = `${LARGEUR_GOUTTIERE} repeat(${jours.length * colonnes.length}, minmax(6.5rem, 1fr))`;

  return (
    <div className="emploi-du-temps relative min-h-0 flex-1 overflow-auto">
      {/* Pas de `min-w-max` : il figerait les colonnes à leur largeur
          minimale et tronquerait les noms alors que la place est là. Le
          `minmax()` suffit — les colonnes s'étirent pour remplir, et ne
          débordent (avec défilement horizontal) qu'une fois le plancher
          atteint, ce qui est le cas de la vue Semaine. */}
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
        {/* Coin : au croisement des deux axes collants. */}
        <div className="sticky left-0 top-0 z-30 border-b border-r border-sand-200 bg-cream-50" />

        {jours.map((jour) => (
          <div
            key={`jour-${jour}`}
            style={{ gridColumn: `span ${colonnes.length}` }}
            className={cn(
              'sticky top-0 z-20 border-b border-r border-sand-200 bg-cream-50 px-2 py-1 text-center text-xs font-semibold text-forest',
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
        <div className="sticky left-0 top-[1.75rem] z-30 border-b border-r border-sand-200 bg-cream-50" />
        {jours.map((jour) =>
          colonnes.map((colonne) => (
            <div
              key={`salle-${jour}-${colonne}`}
              className="sticky top-[1.75rem] z-20 truncate border-b border-r border-sand-200 bg-cream-50 px-1 py-0.5 text-center text-[11px] text-forest/70"
            >
              {parSalle ? (salles[colonne] ?? colonne) : 'Tous les agendas'}
            </div>
          )),
        )}

        {/* La gouttière des heures, collée à gauche. */}
        <div
          className="sticky left-0 z-10 border-r border-sand-200 bg-cream-50"
          style={{ height: HAUTEUR_TOTALE }}
        >
          {heures.map((minute) => (
            <span
              key={minute}
              className="absolute right-1 -translate-y-1/2 text-[10px] tabular-nums text-forest/50"
              style={{ top: (minute - MINUTE_DEBUT) * PX_PAR_MINUTE }}
            >
              {String(Math.floor(minute / 60)).padStart(2, '0')} h
            </span>
          ))}
        </div>

        {jours.map((jour) =>
          colonnes.map((colonne) => {
            const places = parColonne.get(`${jour}::${colonne}`) ?? [];
            return (
              <section
                key={`col-${jour}-${colonne}`}
                aria-label={`${JOUR_COURT.format(new Date(`${jour}T12:00:00`))} — ${
                  parSalle ? (salles[colonne] ?? colonne) : 'tous les agendas'
                }`}
                className="lignes-horaires relative border-r border-sand-200"
                style={{ height: HAUTEUR_TOTALE }}
              >
                {/* Les cartes sont posées en absolu : l'ordre du DOM ne suit
                    l'ordre visuel que si on le force. Il est chronologique,
                    pour que la tabulation parcoure la journée dans l'ordre. */}
                {places.map(({ bloc, voie, voies }) => {
                  const position = placer(bloc.debutMinutes, bloc.finMinutes);
                  if (!position) return null;
                  return (
                    <div
                      key={bloc.cle}
                      className="absolute px-px"
                      style={{
                        top: position.top,
                        left: `${(voie / voies) * 100}%`,
                        width: `${100 / voies}%`,
                      }}
                    >
                      <CarteSeance
                        bloc={bloc}
                        hauteur={position.hauteur}
                        voies={voies}
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
                      className="pointer-events-none absolute inset-x-0 z-10 border-t border-terracotta-500"
                      style={{ top: (maintenant.minutes - MINUTE_DEBUT) * PX_PAR_MINUTE }}
                    />
                  )}
              </section>
            );
          }),
        )}
      </div>
    </div>
  );
}
