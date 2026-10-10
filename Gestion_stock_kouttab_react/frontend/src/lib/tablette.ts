/**
 * Mode « tablette » : l'app stock affichée dans l'écran Personnel de la
 * tablette de caisse (WebView de l'app Android).
 *
 * La tablette ouvre `/tablette#access=…&refresh=…&op=…` après avoir obtenu une
 * session par `POST /auth/caisse/session` (clé de la caisse + nom saisi).
 * Le compte est partagé (« Tablette buvette », rôle AdminStock) ; le nom de la
 * personne signe chaque action côté serveur (« Nom (tablette) »).
 *
 * Le mode est mémorisé dans `sessionStorage` tant que la session tablette est
 * active : pas de menu latéral, Buvette seule, bandeau du nom, cibles tactiles
 * agrandies, pas de déconnexion (c'est la tablette qui gère la sortie).
 */

/** Identifiant du compte système (cf. `backend/app/core/tablette.py`). */
export const USERNAME_TABLETTE = 'tablette_buvette';

const CLE_STOCKAGE = 'kouttab-mode-tablette';

export interface FragmentTablette {
  access: string;
  refresh: string;
  op: string | null;
}

/** Lit `#access=…&refresh=…&op=…` ; `null` si un jeton manque. */
export function lireFragmentTablette(hash: string): FragmentTablette | null {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const access = params.get('access');
  const refresh = params.get('refresh');
  if (!access || !refresh) return null;
  const op = (params.get('op') ?? '').trim();
  return { access, refresh, op: op || null };
}

/** Revendication `op` d'un jeton d'accès (affichage seulement, non vérifié). */
export function operateurDuJeton(jeton: string | null | undefined): string | null {
  if (!jeton) return null;
  const morceau = jeton.split('.')[1];
  if (!morceau) return null;
  try {
    const base64 = morceau.replace(/-/g, '+').replace(/_/g, '/');
    const brut = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '='));
    const octets = Uint8Array.from(brut, (c) => c.charCodeAt(0));
    const charge = JSON.parse(new TextDecoder().decode(octets)) as { op?: unknown };
    return typeof charge.op === 'string' && charge.op ? charge.op : null;
  } catch {
    return null;
  }
}

function stockage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function activerModeTablette(operateur: string): void {
  try {
    stockage()?.setItem(CLE_STOCKAGE, operateur);
  } catch {
    /* stockage indisponible : le mode se déduit encore du compte */
  }
}

export function quitterModeTablette(): void {
  try {
    stockage()?.removeItem(CLE_STOCKAGE);
  } catch {
    /* rien à effacer */
  }
}

/** Nom mémorisé de l'opérateur, ou `null` hors mode tablette. */
export function operateurMemorise(): string | null {
  try {
    return stockage()?.getItem(CLE_STOCKAGE) || null;
  } catch {
    return null;
  }
}
