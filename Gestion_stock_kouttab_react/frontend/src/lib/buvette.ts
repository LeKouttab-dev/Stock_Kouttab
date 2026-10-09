/**
 * Règles d'affichage du suivi de la buvette (paiements, clôture, tablette).
 * Pures, donc testées une fois ici plutôt qu'à travers chaque écran.
 */
import { format, subDays } from 'date-fns';

/** Les paliers proposés sur chaque carte produit. */
export const PALIERS_REAPPRO = [5, 10, 15, 20, 30] as const;

/** Au-delà, la tablette est considérée comme hors ligne (elle écrit toutes les 60 s). */
export const SILENCE_TABLETTE_SECONDES = 5 * 60;

/** Un écart de caisse jusqu'à ce montant (en valeur absolue) est signalé en orange, au-delà en rouge. */
export const ECART_TOLERE_CENTS = 500;

/** Date du jour au format de l'API (`YYYY-MM-DD`), en heure locale. */
export function jourIso(date: Date = new Date()): string {
  return format(date, 'yyyy-MM-dd');
}

/** Les `n` derniers jours, aujourd'hui compris. */
export function periodeGlissante(n: number, aujourdhui: Date = new Date()) {
  return { debut: jourIso(subDays(aujourdhui, n - 1)), fin: jourIso(aujourdhui) };
}

/**
 * « il y a 40 s », « il y a 3 min », « il y a 2 h », « il y a 4 j ».
 * `null` : la tablette ne s'est jamais annoncée.
 */
export function formatDepuis(secondes: number | null | undefined): string {
  if (secondes === null || secondes === undefined) return 'jamais vue';
  const s = Math.max(0, Math.round(secondes));
  if (s < 60) return `il y a ${s} s`;
  const min = Math.floor(s / 60);
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  return `il y a ${Math.floor(h / 24)} j`;
}

export function tabletteSilencieuse(secondes: number | null | undefined): boolean {
  return secondes === null || secondes === undefined || secondes > SILENCE_TABLETTE_SECONDES;
}

export type TonEcart = 'juste' | 'leger' | 'fort';

export function tonEcart(ecartCents: number): TonEcart {
  if (ecartCents === 0) return 'juste';
  return Math.abs(ecartCents) <= ECART_TOLERE_CENTS ? 'leger' : 'fort';
}

export const CLASSES_ECART: Record<TonEcart, string> = {
  juste: 'text-sage-700',
  leger: 'text-orange-600',
  fort: 'text-red-700',
};

/** « +1,50 € » / « −2,00 € » / « 0,00 € » : le signe dit qui doit à qui. */
export function formatEcart(ecartCents: number): string {
  const montant = (Math.abs(ecartCents) / 100).toFixed(2).replace('.', ',');
  if (ecartCents > 0) return `+${montant} €`;
  if (ecartCents < 0) return `−${montant} €`;
  return `${montant} €`;
}

/**
 * Lit un montant saisi en euros (« 12,50 », « 12.5 », « 12 »).
 * `null` si la saisie n'est pas un montant positif ou nul.
 */
export function lireEuros(saisie: string): number | null {
  const propre = saisie.trim().replace(/\s/g, '').replace(',', '.').replace('€', '');
  if (propre === '' || !/^\d+(\.\d{0,2})?$/.test(propre)) return null;
  return Number(propre);
}

/** Contrôle d'adresse volontairement simple : le serveur tient la validation finale. */
export function emailValide(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
