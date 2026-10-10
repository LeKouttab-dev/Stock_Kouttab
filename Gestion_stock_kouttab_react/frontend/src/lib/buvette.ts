/**
 * Règles d'affichage du suivi de la buvette (paiements, clôture, tablette).
 * Pures, donc testées une fois ici plutôt qu'à travers chaque écran.
 */
import { format, subDays } from 'date-fns';
import type { CaisseCategory, EtiquetteType } from '@/types/api';

/** Raccourcis de la fenêtre de réappro : chacun s'ajoute à la quantité saisie. */
export const PALIERS_REAPPRO = [5, 10, 15, 20, 30] as const;

/** Plafond d'un réappro accepté par le serveur. */
export const REAPPRO_MAX = 10_000;

/** « 0,45 » : un montant en centimes, tel qu'on le retape dans un champ en euros. */
export function centsVersSaisie(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || !Number.isFinite(cents)) return '';
  return (cents / 100).toFixed(2).replace('.', ',');
}

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

/* ---- Inventaire ------------------------------------------------------------ */

/** « +2 » / « −3 » / « 0 » : écart d'un produit en unités. */
export function formatEcartUnites(ecart: number): string {
  if (ecart > 0) return `+${ecart}`;
  if (ecart < 0) return `−${Math.abs(ecart)}`;
  return '0';
}

/** Plafond accepté par le serveur pour une quantité comptée. */
export const QUANTITE_MAX = 100_000;

/** Ramène une quantité dans les bornes acceptées (0 à `QUANTITE_MAX`). */
export function bornerQuantite(n: number): number {
  return Math.min(QUANTITE_MAX, Math.max(0, n));
}

/** Quantité saisie au compteur : entier positif ou nul, jamais négatif, plafonné. */
export function lireQuantite(saisie: string): number {
  const chiffres = saisie.replace(/\D/g, '');
  if (chiffres === '') return 0;
  const n = Number.parseInt(chiffres, 10);
  return Number.isFinite(n) ? bornerQuantite(n) : 0;
}

const FUSEAU_PARIS = 'Europe/Paris';

/** « 09/10/2026 22:03 » en heure de Paris, quel que soit le fuseau du navigateur. */
export function formatDateHeureParis(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d
    .toLocaleString('fr-FR', {
      timeZone: FUSEAU_PARIS,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    .replace(',', '');
}

/** Jour (`YYYY-MM-DD`) d'un horodatage, en heure de Paris. */
export function jourParis(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-CA', { timeZone: FUSEAU_PARIS });
}

/** Nom de secours d'un export filtré par période, calqué sur celui du serveur. */
export function nomExportPeriode(prefixe: string, debut: string, fin: string): string {
  if (debut && fin) return `${prefixe}-${debut}_${fin}.xlsx`;
  if (debut) return `${prefixe}-depuis-${debut}.xlsx`;
  if (fin) return `${prefixe}-jusqu-au-${fin}.xlsx`;
  return `${prefixe}-tout.xlsx`;
}

/** Nom de secours de l'export de l'historique des inventaires. */
export function nomExportInventaires(debut: string, fin: string): string {
  return nomExportPeriode('inventaires', debut, fin);
}

export interface LigneComptee {
  id: number;
  nom: string;
  emoji: string | null;
  prix_cents: number;
  stock: number;
  compte: number;
  /** compté − stock en base. */
  ecart: number;
  valeur_cents: number;
}

export interface RecapComptage {
  ecarts: LigneComptee[];
  ecartUnites: number;
  valeurCents: number;
  /** Somme des valeurs négatives, en positif. */
  perteCents: number;
}

/**
 * Récapitulatif avant validation : on compare le compté au stock en base
 * maintenant (le serveur refige ce stock à l'instant de la validation).
 * Un produit supprimé entre-temps (`stock_actuel` nul) n'a plus de stock à corriger.
 */
export function recapComptage(
  lignes: {
    id: number;
    nom: string;
    emoji: string | null;
    prix_cents: number;
    stock_actuel: number | null;
  }[],
  comptes: Record<number, number>,
): RecapComptage {
  const ecarts: LigneComptee[] = [];
  for (const l of lignes) {
    if (l.stock_actuel === null) continue;
    const compte = comptes[l.id] ?? 0;
    const ecart = compte - l.stock_actuel;
    if (ecart === 0) continue;
    ecarts.push({
      id: l.id,
      nom: l.nom,
      emoji: l.emoji,
      prix_cents: l.prix_cents,
      stock: l.stock_actuel,
      compte,
      ecart,
      valeur_cents: ecart * l.prix_cents,
    });
  }
  const ecartUnites = ecarts.reduce((s, e) => s + e.ecart, 0);
  const valeurCents = ecarts.reduce((s, e) => s + e.valeur_cents, 0);
  const perteCents = ecarts.reduce((s, e) => s + (e.valeur_cents < 0 ? -e.valeur_cents : 0), 0);
  return { ecarts, ecartUnites, valeurCents, perteCents };
}

/** « Compte juste » / « Surplus de 2,50 € » / « Manque 3,00 € » (écart = compté − attendu). */
export function libelleEcartEspeces(ecartCents: number): string {
  const montant = `${(Math.abs(ecartCents) / 100).toFixed(2).replace('.', ',')} €`;
  if (ecartCents > 0) return `Surplus de ${montant}`;
  if (ecartCents < 0) return `Manque ${montant}`;
  return 'Compte juste';
}

/**
 * Nom du fichier annoncé par `Content-Disposition` (`filename*=UTF-8''…` ou
 * `filename="…"`). `null` si l'en-tête est absent (non exposé par CORS, par exemple).
 */
export function nomFichierDepuisEntete(entete: string | null | undefined): string | null {
  if (!entete) return null;
  const etendu = /filename\*\s*=\s*(?:[\w-]+'[^']*')?([^;]+)/i.exec(entete);
  if (etendu) {
    try {
      const nom = decodeURIComponent(etendu[1].trim().replace(/^"|"$/g, ''));
      if (nom) return nom;
    } catch {
      // encodage invalide : on se rabat sur `filename=`
    }
  }
  const simple = /filename\s*=\s*"?([^";]+)"?/i.exec(entete);
  return simple ? simple[1].trim() || null : null;
}

/** « Depuis la clôture du … » / « Depuis l'inventaire du … » (heure de Paris), ou null. */
export function libelleDernierComptage(
  dernier: { type: 'cloture' | 'inventaire'; le: string } | null | undefined,
  libelles: { depuisCloture: (d: string) => string; depuisInventaire: (d: string) => string },
): string | null {
  if (!dernier) return null;
  const quand = formatDateHeureParis(dernier.le);
  return dernier.type === 'cloture'
    ? libelles.depuisCloture(quand)
    : libelles.depuisInventaire(quand);
}

/** Ordre des groupes de l'onglet Produits : celui de la tablette, puis le reste. */
export const GROUPES_PRODUITS = ['sucre_sale', 'boissons', 'cafe', 'epicerie', 'aucun'] as const;
export type GroupeProduits = (typeof GROUPES_PRODUITS)[number];

/** Normalise pour la recherche : minuscules, sans accents. */
function sansAccents(texte: string): string {
  return texte.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Le produit correspond-il à la recherche (nom ou code-barres) ? */
export function produitCorrespond(
  produit: { name: string; barcode?: string | null },
  recherche: string,
): boolean {
  const r = sansAccents(recherche.trim());
  if (!r) return true;
  return sansAccents(produit.name).includes(r) || (produit.barcode ?? '').includes(r);
}

/**
 * Produits rangés par onglet de la tablette, dans l'ordre de la tablette, puis
 * « Hors tablette » (sans onglet ou onglet inconnu). Groupes vides retirés ;
 * dans un groupe, l'ordre reçu est conservé.
 */
export function grouperProduits<P extends { caisse_category?: string | null }>(
  produits: P[],
): { groupe: GroupeProduits; produits: P[] }[] {
  const connus = new Set<string>(GROUPES_PRODUITS);
  const groupes = new Map<GroupeProduits, P[]>(GROUPES_PRODUITS.map((g) => [g, []]));
  for (const p of produits) {
    const cle = (
      p.caisse_category && connus.has(p.caisse_category) ? p.caisse_category : 'aucun'
    ) as GroupeProduits;
    groupes.get(cle)?.push(p);
  }
  return GROUPES_PRODUITS.map((groupe) => ({ groupe, produits: groupes.get(groupe) ?? [] })).filter(
    (g) => g.produits.length > 0,
  );
}

/* ---- Menu de la tablette : ordre et étiquettes ---------------------------- */

/** Onglets de la tablette, dans l'ordre où elle les affiche. */
export const ONGLETS_MENU: readonly CaisseCategory[] = [
  'sucre_sale',
  'boissons',
  'cafe',
  'epicerie',
];

/** Périodes proposées pour « Trier par ventes », en jours. */
export const PERIODES_TRI_VENTES = [7, 30, 90] as const;

/** Étiquettes à libellé fixe ; `libre` porte son propre texte. */
export const ETIQUETTES_FIXES = [
  'nouveaute',
  'edition_limitee',
  'derniers',
  'coup_de_coeur',
  'promo',
] as const satisfies readonly EtiquetteType[];

/** Longueur maximale d'une étiquette libre (caractères), comme le serveur. */
export const ETIQUETTE_TEXTE_MAX = 20;

/**
 * Couleurs des pastilles, reprises par la tablette : Nouveauté vert, Édition
 * limitée violet, Derniers exemplaires orange, Coup de cœur rouge doux, Promo
 * or, texte libre gris foncé.
 */
export const COULEURS_ETIQUETTE: Record<EtiquetteType, string> = {
  nouveaute: 'bg-green-600 text-white',
  edition_limitee: 'bg-violet-600 text-white',
  derniers: 'bg-orange-500 text-white',
  coup_de_coeur: 'bg-rose-500 text-white',
  promo: 'bg-amber-500 text-white',
  libre: 'bg-gray-700 text-white',
};

/** Texte libre tel que le serveur l'enregistrera : espaces réduits, bords retirés. */
export function nettoyerEtiquette(texte: string): string {
  return texte.replace(/\s+/g, ' ').trim();
}

/**
 * Longueur comptée comme le serveur (en caractères, pas en unités UTF-16) :
 * un emoji compte pour un.
 */
export function longueurEtiquette(texte: string): number {
  return Array.from(nettoyerEtiquette(texte)).length;
}

/**
 * Produits affichés par la tablette dans un onglet, dans son ordre : actifs,
 * rangés d'abord (`ordre_caisse`), les autres ensuite, par nom.
 */
export function produitsDuMenu<
  P extends {
    id: number;
    name: string;
    is_active: boolean;
    caisse_category?: string | null;
    ordre_caisse?: number | null;
  },
>(produits: P[], categorie: CaisseCategory): P[] {
  const rang = (p: P) => p.ordre_caisse ?? Number.POSITIVE_INFINITY;
  return produits
    .filter((p) => p.is_active && p.caisse_category === categorie)
    .sort((a, b) => rang(a) - rang(b) || a.name.localeCompare(b.name, 'fr') || a.id - b.id);
}

/** Copie de la liste où l'élément `de` a été déplacé à la position `vers`. */
export function deplacer<T>(liste: readonly T[], de: number, vers: number): T[] {
  const copie = [...liste];
  if (de < 0 || de >= copie.length || vers < 0 || vers >= copie.length) return copie;
  const [element] = copie.splice(de, 1);
  copie.splice(vers, 0, element);
  return copie;
}

/** Ids d'un ordre proposé, puis ceux qu'il ne connaît pas (dans l'ordre actuel). */
export function appliquerOrdrePropose(
  actuels: readonly number[],
  propose: readonly number[],
): number[] {
  const connus = new Set(actuels);
  const tete = propose.filter((id) => connus.has(id));
  const vus = new Set(tete);
  return [...tete, ...actuels.filter((id) => !vus.has(id))];
}
