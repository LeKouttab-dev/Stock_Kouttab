/**
 * Le calcul de la grille d'emploi du temps : placer, empiler, fusionner.
 *
 * Tout est pur et sans React — c'est ce qui permet de vérifier le placement
 * d'un cours à cheval sur la fin de grille, huit chevauchements simultanés ou
 * la fusion de douze rendez-vous de cinq minutes sans monter un composant.
 *
 * **Pourquoi une grille maison plutôt que FullCalendar** : les colonnes par
 * ressource (une par salle) appartiennent à FullCalendar Premium, sous licence
 * payante. Le cas est ici très contraint — lecture seule, 8 h–22 h 30, un seul
 * fuseau, aucun événement « journée entière » — ce qui rend le composant bon
 * marché. FullCalendar reste en place pour les vues Mois et Liste.
 */
import type { EvenementCalendrier } from '@/types/api';

/** Amplitude de la grille. Relevé réel : premier début 08:30, dernière fin 22:15. */
export const MINUTE_DEBUT = 8 * 60;
export const MINUTE_FIN = 22 * 60 + 30;
export const PX_PAR_MINUTE = 1;

/** En dessous, aucun texte ne tient et la carte n'est plus cliquable. */
export const HAUTEUR_MIN = 22;

/**
 * Un créneau de moins de ça n'est pas un cours : les permanences
 * administratives sont des rendez-vous de paiement de cinq minutes. Sur une
 * grille de quatorze heures, un tel créneau fait un demi-pourcent de la
 * hauteur — un filet invisible, et il y en a vingt dans la journée.
 */
export const MINUTES_MICRO_CRENEAU = 15;

/** Écart maximal entre deux micro-créneaux d'une même plage. */
const ECART_MAX_FUSION = 30;

/**
 * Le fuseau de l'institut, imposé comme dans `lib/calendrier.ts`.
 *
 * **Ne jamais passer par `new Date(iso).getHours()`** : ce serait le fuseau du
 * navigateur. L'intégration continue tourne en UTC, et un cours de 17:30
 * s'afficherait à 15:30 sans que rien ne le signale — c'est exactement le bug
 * déjà corrigé sur `formatPlage`.
 */
const FUSEAU = 'Europe/Paris';

// Lu par `formatToParts`, et non en découpant la chaîne : `fr-CA` rend
// « 2026-10-14 17 h 30 », et la ponctuation d'une locale change d'une version
// d'ICU à l'autre. Les parts, elles, sont nommées.
const HORLOGE = new Intl.DateTimeFormat('fr-CA', {
  timeZone: FUSEAU,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export interface InstantParis {
  /** `AAAA-MM-JJ`, le jour tel qu'il est à Paris. */
  jour: string;
  /** Minutes depuis minuit, heure de Paris. */
  minutes: number;
}

export function minutesParis(iso: string): InstantParis {
  const parts: Record<string, string> = {};
  for (const part of HORLOGE.formatToParts(new Date(iso))) {
    if (part.type !== 'literal') parts[part.type] = part.value;
  }
  // Certains moteurs rendent « 24 » pour minuit plutôt que « 00 ».
  const heures = Number(parts.hour) % 24;
  return {
    jour: `${parts.year}-${parts.month}-${parts.day}`,
    minutes: heures * 60 + Number(parts.minute),
  };
}

export interface Position {
  top: number;
  hauteur: number;
}

/**
 * Où poser une carte, en pixels depuis le haut de la grille.
 *
 * Rend `null` pour ce qui tombe **entièrement** hors de 08:00–22:30. Ces
 * événements ne sont pas perdus pour autant : l'écran les rassemble dans une
 * bande « hors plage » sous l'en-tête du jour. Un cours de 7 h ajouté à la
 * rentrée prochaine ne doit pas disparaître sans bruit.
 */
export function placer(debutMinutes: number, finMinutes: number): Position | null {
  const haut = Math.max(debutMinutes, MINUTE_DEBUT);
  const bas = Math.min(finMinutes, MINUTE_FIN);
  if (bas <= haut) return null;
  return {
    top: (haut - MINUTE_DEBUT) * PX_PAR_MINUTE,
    hauteur: Math.max(HAUTEUR_MIN, (bas - haut) * PX_PAR_MINUTE),
  };
}

/**
 * Un bloc de la grille : un cours, ou une plage de micro-créneaux fusionnés.
 */
export interface BlocGrille {
  cle: string;
  /** Un seul élément dans le cas courant ; N pour une plage fusionnée. */
  evenements: EvenementCalendrier[];
  debutMinutes: number;
  finMinutes: number;
  jour: string;
}

function bornesDe(evenement: EvenementCalendrier): { jour: string; debut: number; fin: number } {
  const debut = minutesParis(evenement.debut);
  const fin = minutesParis(evenement.fin);
  return {
    jour: debut.jour,
    debut: debut.minutes,
    // Un événement qui franchit minuit est coupé en bas de grille plutôt que
    // de produire une hauteur négative.
    fin: fin.jour === debut.jour ? fin.minutes : MINUTE_FIN,
  };
}

/**
 * Regroupe les micro-créneaux consécutifs d'un même agenda en une seule carte.
 *
 * Les permanences administratives sont une vingtaine de rendez-vous de cinq
 * minutes à la suite. Rendus un par un, ce sont des filets d'un pixel qu'on ne
 * peut ni lire ni cliquer ; fusionnés, c'est « Permanence administrative,
 * 12:00–13:00, 12 créneaux », et le détail s'ouvre au clic.
 *
 * Ne fusionne **que** des créneaux courts du même agenda : deux cours d'une
 * heure qui se suivent restent deux cartes, parce que ce sont deux cours.
 */
export function fusionnerMicroCreneaux(evenements: EvenementCalendrier[]): BlocGrille[] {
  const blocs: BlocGrille[] = [];
  const restants: EvenementCalendrier[] = [];
  const parAgenda = new Map<string, EvenementCalendrier[]>();

  for (const evenement of evenements) {
    const { debut, fin } = bornesDe(evenement);
    if (fin - debut > MINUTES_MICRO_CRENEAU) {
      restants.push(evenement);
      continue;
    }
    const liste = parAgenda.get(evenement.agenda_id) ?? [];
    liste.push(evenement);
    parAgenda.set(evenement.agenda_id, liste);
  }

  for (const evenement of restants) {
    const { jour, debut, fin } = bornesDe(evenement);
    blocs.push({
      cle: `${evenement.agenda_id}::${evenement.id}`,
      evenements: [evenement],
      debutMinutes: debut,
      finMinutes: fin,
      jour,
    });
  }

  for (const liste of parAgenda.values()) {
    const tries = [...liste].sort((a, b) => bornesDe(a).debut - bornesDe(b).debut);
    let plage: EvenementCalendrier[] = [];
    let debutPlage = 0;
    let finPlage = 0;
    let jourPlage = '';

    const pousser = () => {
      if (!plage.length) return;
      const premier = plage[0];
      blocs.push({
        cle: `${premier.agenda_id}::plage::${premier.id}`,
        evenements: plage,
        debutMinutes: debutPlage,
        finMinutes: finPlage,
        jour: jourPlage,
      });
      plage = [];
    };

    for (const evenement of tries) {
      const { jour, debut, fin } = bornesDe(evenement);
      const suite =
        plage.length > 0 && jour === jourPlage && debut - finPlage <= ECART_MAX_FUSION;
      if (suite) {
        finPlage = Math.max(finPlage, fin);
      } else {
        pousser();
        debutPlage = debut;
        finPlage = fin;
        jourPlage = jour;
      }
      plage.push(evenement);
    }
    pousser();
  }

  return blocs.sort((a, b) => a.debutMinutes - b.debutMinutes);
}

export interface EnVoie {
  bloc: BlocGrille;
  /** Index de la sous-colonne, de 0 à `voies - 1`. */
  voie: number;
  /** Nombre de sous-colonnes de la grappe. Le même pour tous ses membres. */
  voies: number;
}

/**
 * Répartit en sous-colonnes les blocs qui se chevauchent dans une colonne.
 *
 * Une salle n'accueille qu'un cours à la fois : dans le cas courant, `voies`
 * vaut 1. C'est un filet — et il sert surtout la colonne « Autre », qui
 * rassemble tout ce qui n'a pas de salle. Sur les données réelles, on y a vu
 * jusqu'à **huit événements simultanés**.
 *
 * `voies` est le compte de la **grappe** entière, identique pour tous ses
 * membres : avec un compte par bloc, deux cartes de la même bande auraient des
 * largeurs différentes et l'œil lirait un bug.
 */
export function repartirEnVoies(blocs: BlocGrille[]): EnVoie[] {
  const tries = [...blocs].sort(
    (a, b) =>
      a.debutMinutes - b.debutMinutes || b.finMinutes - b.debutMinutes - (a.finMinutes - a.debutMinutes),
  );

  const resultat: EnVoie[] = [];
  let grappe: EnVoie[] = [];
  let finsDesVoies: number[] = [];

  const clore = () => {
    const voies = finsDesVoies.length || 1;
    for (const place of grappe) resultat.push({ ...place, voies });
    grappe = [];
    finsDesVoies = [];
  };

  for (const bloc of tries) {
    // La grappe se vide quand plus rien ne déborde sur ce bloc : on est alors
    // devant un ensemble transitivement chevauchant, clos.
    if (finsDesVoies.length && finsDesVoies.every((fin) => fin <= bloc.debutMinutes)) clore();

    let voie = finsDesVoies.findIndex((fin) => fin <= bloc.debutMinutes);
    if (voie === -1) {
      voie = finsDesVoies.length;
      finsDesVoies.push(bloc.finMinutes);
    } else {
      finsDesVoies[voie] = bloc.finMinutes;
    }
    grappe.push({ bloc, voie, voies: 1 });
  }
  clore();

  return resultat;
}

/** En dessous, ce n'est pas un cours : c'est un créneau qui se pose par-dessus. */
export const MINUTES_COURS = 30;

/** Où commence la zone des créneaux posés sur un cours, en % de la colonne. */
const DEBUT_ZONE_SUPERPOSEE = 50;

export interface Disposition {
  bloc: BlocGrille;
  /** Bord gauche, en % de la colonne. */
  gauche: number;
  /** Largeur, en % de la colonne. */
  largeur: number;
  /** Ordre d'empilement : les créneaux courts passent au-dessus des cours. */
  plan: number;
  /**
   * Hauteur, en px, que des créneaux posés couvrent en haut de ce cours. La
   * carte descend son titre d'autant : sinon « Madrassah N 2 » disparaît sous
   * deux rendez-vous posés à 13:30.
   */
  retraitHaut: number;
}

function estUnCours(bloc: BlocGrille): boolean {
  return bloc.evenements.length === 1 && bloc.finMinutes - bloc.debutMinutes >= MINUTES_COURS;
}

/**
 * La fin **telle qu'elle s'affiche**. Un rendez-vous de cinq minutes est
 * dessiné sur `HAUTEUR_MIN` pixels, soit plus de vingt minutes de grille : un
 * créneau 13:25–13:30 déborde visuellement sur le cours qui commence à 13:30.
 * Le juger « sans cours dessous » sur ses horaires réels le mettait pleine
 * largeur par-dessus le titre du cours.
 */
function finVisuelle(bloc: BlocGrille): number {
  return Math.max(bloc.finMinutes, bloc.debutMinutes + HAUTEUR_MIN / PX_PAR_MINUTE);
}

function chevauche(a: BlocGrille, b: BlocGrille): boolean {
  return a.debutMinutes < finVisuelle(b) && b.debutMinutes < finVisuelle(a);
}

/** Répartit en voies sur l'étendue visuelle, pour que deux cartes ne se recouvrent pas. */
function enVoiesVisuelles(blocs: BlocGrille[]): EnVoie[] {
  const parCle = new Map(blocs.map((b) => [b.cle, b]));
  return repartirEnVoies(blocs.map((b) => ({ ...b, finMinutes: finVisuelle(b) }))).map((p) => ({
    ...p,
    bloc: parCle.get(p.bloc.cle) ?? p.bloc,
  }));
}

function dansLaZone(places: EnVoie[], debut: number, plan: number): Disposition[] {
  const etendue = 100 - debut;
  return places.map(({ bloc, voie, voies }) => ({
    bloc,
    gauche: debut + (voie / voies) * etendue,
    largeur: etendue / voies,
    plan,
    retraitHaut: 0,
  }));
}

/**
 * Dispose une colonne comme Google Agenda : **le long dessous, le court
 * par-dessus**.
 *
 * Tout mettre côte à côte réduisait un cours de deux heures à « C… » dès que
 * deux rendez-vous de cinq minutes tombaient à son début (mercredi 14/10,
 * 17:30, Maziri). Deux couches, donc :
 *
 * - **les cours** (30 min et plus) se partagent la largeur en voies, comme
 *   avant — deux vrais cours au même moment dans la même salle sont un conflit
 *   réel, et côte à côte est la bonne façon de le montrer ;
 * - **les créneaux courts** et les plages fusionnées ne prennent pas de voie.
 *   Posés sur un cours, ils occupent sa moitié droite, au-dessus : le titre du
 *   cours reste lisible à gauche. Sans cours dessous, ils prennent toute la
 *   largeur — rien à préserver, inutile de perdre la moitié de la place.
 */
export function disposer(blocs: BlocGrille[]): Disposition[] {
  const cours = blocs.filter(estUnCours);
  const courts = blocs.filter((b) => !estUnCours(b));
  const surUnCours = courts.filter((c) => cours.some((k) => chevauche(c, k)));
  const libres = courts.filter((c) => !surUnCours.includes(c));

  // Ce que les créneaux posés couvrent du haut de chaque cours : ceux qui
  // commencent avant que le titre ait pu s'afficher (dans ses 30 premières
  // minutes) et débordent sur son début.
  const placesCours = dansLaZone(repartirEnVoies(cours), 0, 1).map((place) => {
    const debut = place.bloc.debutMinutes;
    const couvert = surUnCours
      .filter((c) => c.debutMinutes < debut + MINUTES_COURS && finVisuelle(c) > debut)
      .reduce((max, c) => Math.max(max, (finVisuelle(c) - debut) * PX_PAR_MINUTE), 0);
    return { ...place, retraitHaut: couvert };
  });

  return [
    ...placesCours,
    ...dansLaZone(enVoiesVisuelles(libres), 0, 2),
    ...dansLaZone(enVoiesVisuelles(surUnCours), DEBUT_ZONE_SUPERPOSEE, 3),
  ].sort((a, b) => a.bloc.debutMinutes - b.bloc.debutMinutes || a.plan - b.plan);
}

/**
 * La clé de colonne d'un événement : sa salle, ou la première du référentiel.
 *
 * Le serveur range déjà en Maziri ce qui n'a pas de salle (`salle_source =
 * "defaut"`). Ce repli ne couvre que l'improbable — une clé que la grille ne
 * connaît pas — et il vaut mieux une carte mal rangée qu'une colonne fantôme.
 */
export function colonneDe(evenement: EvenementCalendrier, salles: Record<string, string>): string {
  const salle = evenement.salle;
  if (salle && salle in salles) return salle;
  return Object.keys(salles)[0] ?? 'maziri';
}

/** Les jours d'une vue, en `AAAA-MM-JJ` (heure de Paris). */
export function joursDeLaVue(ancre: Date, nombre: number): string[] {
  const jours: string[] = [];
  for (let i = 0; i < nombre; i += 1) {
    const jour = new Date(ancre);
    jour.setDate(jour.getDate() + i);
    jours.push(minutesParis(jour.toISOString()).jour);
  }
  return jours;
}

/** `17:30` à partir de minutes depuis minuit. */
export function enHeure(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
