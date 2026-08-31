/**
 * Passage signé depuis gestion.lekouttab.fr.
 *
 * Le jeton arrive dans le FRAGMENT de l'URL (`/sso#jeton=…`) et jamais en
 * query string : le fragment n'est pas envoyé au serveur, il n'atterrit donc
 * ni dans les journaux Caddy ni dans ceux du backend, qui consignent les URL
 * complètes.
 */

/** Extrait le jeton du fragment. Alphabet JWT strict : rien d'autre ne passe. */
export function jetonDepuisFragment(hash: string): string | null {
  const m = /[#&]jeton=([A-Za-z0-9_.-]+)(?:&|$)/.exec(hash ?? '');
  return m ? m[1] : null;
}

export interface SsoPrefill {
  evenement?: string;
  date_evenement?: string;
}

/**
 * Préremplissage de la note de frais, transmis à côté du jeton quand le
 * passage part de la page d'un événement (gestion). Données d'affichage
 * uniquement : rien de signé, rien de sensible — l'utilisateur peut de toute
 * façon tout éditer dans le formulaire.
 */
export function prefillDepuisFragment(hash: string): SsoPrefill {
  const prefill: SsoPrefill = {};
  const ev = /[#&]evenement=([^&]*)/.exec(hash ?? '');
  if (ev && ev[1]) {
    try {
      const valeur = decodeURIComponent(ev[1]).slice(0, 255).trim();
      if (valeur) prefill.evenement = valeur;
    } catch {
      /* fragment illisible : tant pis pour le prefill, jamais pour le passage */
    }
  }
  const date = /[#&]date_evenement=(\d{4}-\d{2}-\d{2})(?:&|$)/.exec(hash ?? '');
  if (date) prefill.date_evenement = date[1];
  return prefill;
}
