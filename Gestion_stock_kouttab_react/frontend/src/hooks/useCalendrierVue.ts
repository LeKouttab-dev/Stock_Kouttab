import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { minutesParis } from '@/lib/calendrier-grille';

export type VueCalendrier = 'mois' | 'semaine' | 'trois-jours' | 'jour' | 'liste';

/** Combien de jours chaque vue de grille affiche. */
export const JOURS_PAR_VUE: Record<string, number> = {
  semaine: 7,
  'trois-jours': 3,
  jour: 1,
};

const CLE_VUE = 'calendrier.vue';
const CLE_SALLES = 'calendrier.salles-masquees';

/**
 * Le point de rupture `lg` de Tailwind, en JavaScript.
 *
 * **Le seul media-query en JS du dépôt**, et il lui faut une raison : le
 * nombre de jours affichés est une *donnée* passée à la grille, pas un style.
 * Aucune classe `lg:` ne sait le produire. Tout le reste du responsive reste
 * en Tailwind pur, avec `lg` comme unique charnière.
 *
 * Doit rester égal au `lg` de `tailwind.config.ts`.
 */
const COMPACT = '(max-width: 1023px)';

export function useEstCompact(): boolean {
  return useSyncExternalStore(
    (changement) => {
      const liste = window.matchMedia(COMPACT);
      liste.addEventListener('change', changement);
      return () => liste.removeEventListener('change', changement);
    },
    () => window.matchMedia(COMPACT).matches,
    () => false,
  );
}

/** La minute courante, pour le trait « maintenant ». */
export function useMaintenant() {
  const [instant, setInstant] = useState(() => new Date());
  useEffect(() => {
    const minuterie = setInterval(() => setInstant(new Date()), 60_000);
    return () => clearInterval(minuterie);
  }, []);
  return useMemo(() => minutesParis(instant.toISOString()), [instant]);
}

function lire<T extends string>(cle: string, valide: readonly T[], defaut: T): T {
  try {
    const brut = localStorage.getItem(cle) as T | null;
    return brut && valide.includes(brut) ? brut : defaut;
  } catch {
    return defaut;
  }
}

const VUES: readonly VueCalendrier[] = ['mois', 'semaine', 'trois-jours', 'jour', 'liste'];

/**
 * La vue affichée et la date d'ancrage.
 *
 * **« 3 jours » est le défaut**, et non la semaine : sept jours fois quatre
 * salles font vingt-huit colonnes, soit une cinquantaine de pixels chacune sur
 * un écran de bureau — une carte de cours n'y tient pas. Trois jours en font
 * douze, largement lisibles une fois les panneaux repliés.
 *
 * Sur un écran étroit, « Semaine » sert la liste de la semaine, **sans écraser
 * la préférence** : le réglage du poste de travail doit survivre à une
 * consultation sur téléphone.
 */
export function useCalendrierVue() {
  const compact = useEstCompact();
  const [memorisee, setMemorisee] = useState<VueCalendrier>(() =>
    lire(CLE_VUE, VUES, 'trois-jours'),
  );
  const [ancre, setAncre] = useState(() => new Date());

  // Sur téléphone, une grille de sept jours n'a pas la place d'une carte :
  // « Semaine » y sert la LISTE de la semaine. Trois jours tiennent, eux.
  const vue: VueCalendrier = compact && memorisee === 'semaine' ? 'liste' : memorisee;

  const choisir = useCallback((suivante: VueCalendrier) => {
    setMemorisee(suivante);
    try {
      localStorage.setItem(CLE_VUE, suivante);
    } catch {
      /* sans effet */
    }
  }, []);

  const decaler = useCallback(
    (sens: -1 | 1) =>
      setAncre((actuelle) => {
        const suivante = new Date(actuelle);
        const pas = vue === 'mois' ? 0 : (JOURS_PAR_VUE[vue] ?? 7);
        if (vue === 'mois') suivante.setMonth(suivante.getMonth() + sens);
        else suivante.setDate(suivante.getDate() + sens * pas);
        return suivante;
      }),
    [vue],
  );

  return {
    vue,
    /** La vue choisie, avant l'adaptation au téléphone : c'est elle que la barre montre active. */
    choisie: memorisee,
    choisir,
    ancre,
    setAncre,
    decaler,
    aujourdhui: () => setAncre(new Date()),
  };
}

/** Les salles décochées, retenues d'une visite à l'autre. */
export function useSallesMasquees() {
  const [masquees, setMasquees] = useState<string[]>(() => {
    try {
      const brut = localStorage.getItem(CLE_SALLES);
      return brut ? (JSON.parse(brut) as string[]) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(CLE_SALLES, JSON.stringify(masquees));
    } catch {
      /* sans effet */
    }
  }, [masquees]);

  const basculer = useCallback(
    (cle: string) =>
      setMasquees((actuelles) =>
        actuelles.includes(cle) ? actuelles.filter((m) => m !== cle) : [...actuelles, cle],
      ),
    [],
  );

  return { masquees, basculer };
}
