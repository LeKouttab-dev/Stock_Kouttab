/**
 * Périodes prédéfinies des écrans de la buvette (Paiements, Statistiques,
 * Réappros, historiques Clôture et Inventaire).
 *
 * Les dates sont des JOURS DE PARIS (`YYYY-MM-DD`), comme les filtres de
 * l'API : à 0 h 30 à Paris, « aujourd'hui » est déjà le lendemain même si le
 * navigateur est réglé sur un autre fuseau.
 */

export type PresetPeriode = 'aujourdhui' | '7j' | 'mois' | '3mois' | 'perso';

export const PRESETS_PERIODE: readonly PresetPeriode[] = [
  'aujourdhui',
  '7j',
  'mois',
  '3mois',
  'perso',
] as const;

export interface PeriodeChoisie {
  preset: PresetPeriode;
  /** Jour de Paris, `YYYY-MM-DD`, inclus. */
  debut: string;
  /** Jour de Paris, `YYYY-MM-DD`, inclus. */
  fin: string;
}

/** Jour de Paris (`YYYY-MM-DD`) d'un instant. */
export function jourDeParis(instant: Date = new Date()): string {
  return instant.toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
}

function enParties(jour: string): [number, number, number] {
  const [a, m, j] = jour.split('-').map(Number);
  return [a, m, j];
}

function versJour(a: number, m: number, j: number): string {
  const d = new Date(Date.UTC(a, m - 1, j));
  return d.toISOString().slice(0, 10);
}

/** `jour` décalé de `n` jours (calendrier, sans fuseau). */
export function ajouterJours(jour: string, n: number): string {
  const [a, m, j] = enParties(jour);
  return versJour(a, m, j + n);
}

/** `jour` décalé de `n` mois, le quantième ramené à la fin du mois si besoin. */
export function ajouterMois(jour: string, n: number): string {
  const [a, m, j] = enParties(jour);
  const dernierDuMois = new Date(Date.UTC(a, m - 1 + n + 1, 0)).getUTCDate();
  return versJour(a, m + n, Math.min(j, dernierDuMois));
}

/**
 * Bornes d'une période prédéfinie. `perso` n'a pas de bornes propres : il
 * garde `actuelle` (les dates affichées au moment du choix).
 */
export function bornesPreset(
  preset: PresetPeriode,
  maintenant: Date = new Date(),
  actuelle?: { debut: string; fin: string },
): { debut: string; fin: string } {
  const aujourdhui = jourDeParis(maintenant);
  switch (preset) {
    case 'aujourdhui':
      return { debut: aujourdhui, fin: aujourdhui };
    case '7j':
      return { debut: ajouterJours(aujourdhui, -6), fin: aujourdhui };
    case 'mois':
      return { debut: `${aujourdhui.slice(0, 8)}01`, fin: aujourdhui };
    case '3mois':
      return { debut: ajouterJours(ajouterMois(aujourdhui, -3), 1), fin: aujourdhui };
    case 'perso':
      return actuelle
        ? { debut: actuelle.debut, fin: actuelle.fin }
        : { debut: `${aujourdhui.slice(0, 8)}01`, fin: aujourdhui };
  }
}

export function periodeInitiale(
  preset: PresetPeriode,
  maintenant: Date = new Date(),
): PeriodeChoisie {
  return { preset, ...bornesPreset(preset, maintenant) };
}
