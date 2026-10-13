/**
 * Les pages qui prennent toute la largeur, et gèrent leur propre défilement.
 *
 * Le cap `max-w-7xl` d'`AppLayout` sert toutes les pages : le retirer pour une
 * seule les déborderait toutes. On le conditionne donc à la route, et non à un
 * contexte posé par la page — un contexte arrive après le premier rendu, soit
 * une frame de mauvaise mise en page, et c'est précisément la frame où une
 * grille mesure ses colonnes.
 *
 * La même liste décide du repli par défaut de la barre latérale : une seule
 * source pour les deux comportements, qui répondent à la même question.
 */
export const PAGES_PLEINE_LARGEUR = ['/calendar'] as const;

export function estPleineLargeur(chemin: string): boolean {
  return PAGES_PLEINE_LARGEUR.some(
    (page) => chemin === page || chemin.startsWith(`${page}/`),
  );
}
