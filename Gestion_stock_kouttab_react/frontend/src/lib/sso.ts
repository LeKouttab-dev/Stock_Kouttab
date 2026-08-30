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
