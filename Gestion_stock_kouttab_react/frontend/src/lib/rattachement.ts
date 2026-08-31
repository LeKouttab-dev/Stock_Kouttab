import type { AppEvent, Pole } from '@/types/api';

/**
 * Le pôle EV correspondant à la famille d'un événement.
 *
 * Le titre HelloAsso porte la lettre entre parenthèses — « Sortie pédagogique à
 * la ferme (J) » —, le backend en déduit `type_ev` à la synchronisation, et
 * c'est cette lettre qui désigne le pôle : `J` → EV(J).
 *
 * Le rapprochement passe par `type_evenement`, **jamais par le nom du pôle**.
 * Reconnaître « EV(J) » au texte marcherait aujourd'hui et casserait le jour où
 * un pôle est renommé — or les pôles sont un référentiel administrable, fait
 * pour bouger sans redéploiement.
 *
 * Rend `null` quand la famille est inconnue ou qu'aucun pôle actif ne la porte.
 * Le formulaire redonne alors la main : mieux vaut demander que rattacher une
 * pièce comptable au mauvais pôle, une erreur qui ne se voit qu'à la clôture.
 */
export function polePourEvenement(
  poles: Pole[] | undefined,
  typeEv: string | null | undefined,
): Pole | null {
  if (!poles || !typeEv) return null;
  const famille = typeEv.trim().toUpperCase();
  if (!famille) return null;

  const candidats = poles.filter(
    (p) =>
      p.is_active &&
      p.requiert_evenement &&
      (p.type_evenement ?? '').trim().toUpperCase() === famille,
  );

  // Deux pôles actifs pour la même famille : la configuration est ambiguë, et
  // en choisir un au hasard produirait une imputation fausse un jour sur deux.
  // On rend la main plutôt que de trancher à la place du comptable.
  return candidats.length === 1 ? candidats[0] : null;
}

/**
 * Les pôles proposés quand la dépense n'est liée à aucun événement.
 *
 * Frais généraux, Institut, Halaqa, Séjour annuel, ESP-VT — tout ce qui ne
 * réclame pas d'événement. Les pôles EV en sont exclus : ils ne s'atteignent
 * plus qu'en choisissant l'événement, faute de quoi on pourrait poser EV(T) sur
 * une pièce sans le moindre événement, que l'API refuserait ensuite.
 */
export function polesSansEvenement(poles: Pole[] | undefined): Pole[] {
  return (poles ?? []).filter((p) => p.is_active && !p.requiert_evenement);
}

/** Comparaison de titres tolérante aux écarts de saisie. */
function normaliser(titre: string): string {
  return titre.trim().toLowerCase().replace(/\s+/g, ' ');
}

/**
 * Retrouve, dans le référentiel, l'événement désigné par un titre.
 *
 * Sert au passage signé depuis l'outil de gestion : il transporte le **titre**
 * de l'événement, pas son identifiant. Le retrouver vaut mieux que de le
 * recopier en saisie libre, pour deux raisons — la pièce se rattache à la vraie
 * ligne du référentiel plutôt qu'à une chaîne de caractères, et son `type_ev`
 * déjà déduit par le backend désigne alors le pôle sans rien parser ici.
 *
 * C'est ce qui évite d'écrire côté front un second lecteur de « (T)/(G)/(J) » :
 * ce dépôt compte déjà deux paires de modules jumeaux (`naming`, `money`) et
 * chacune est une occasion de diverger. La lettre est lue à un seul endroit, à
 * la synchronisation.
 *
 * Rend `null` si rien ne correspond — le titre part alors en saisie libre,
 * comme avant, et le formulaire redemande le pôle.
 */
export function evenementParTitre(
  events: AppEvent[] | undefined,
  titre: string | null | undefined,
): AppEvent | null {
  if (!events || !titre) return null;
  const recherche = normaliser(titre);
  if (!recherche) return null;

  const correspondants = events.filter((e) => normaliser(e.nom) === recherche);
  // Deux événements du même nom : on ne devine pas lequel, le déposant tranche.
  return correspondants.length === 1 ? correspondants[0] : null;
}
