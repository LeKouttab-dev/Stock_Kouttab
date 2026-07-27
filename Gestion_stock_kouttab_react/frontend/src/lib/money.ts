/**
 * Calculs monétaires du domaine.
 *
 * Ces règles étaient recopiées dans les composants qui en avaient besoin :
 * une correction sur l'une ne se propageait pas aux autres. Regroupées ici,
 * elles sont testées une fois et appliquées partout.
 */

/**
 * Montant réellement dû au bénévole pour une note de frais.
 *
 * On soustrait ce qui a déjà été remboursé (avance en espèces, par exemple)
 * et la remise éventuelle obtenue chez le fournisseur.
 *
 * Le résultat est borné à 0 : un « remboursement » négatif n'a pas de sens et
 * s'afficherait comme une dette du bénévole envers l'association.
 */
export function expenseTotal(expense: {
  montant: number | string;
  remboursement_deja_emis?: number | string | null;
  remise?: number | string | null;
}): number {
  const montant = Number(expense.montant) || 0;
  const rembourse = Number(expense.remboursement_deja_emis) || 0;
  const remise = Number(expense.remise) || 0;
  return Math.max(0, montant - rembourse - remise);
}

/**
 * Convertit un montant en euros vers des centimes entiers.
 *
 * `Math.round` est indispensable : `19.99 * 100` vaut 1998.9999999999998 en
 * virgule flottante, et une troncature donnerait 1998 centimes.
 */
export function eurosToCents(euros: number | string): number {
  const value = Number(euros);
  return Number.isFinite(value) ? Math.round(value * 100) : 0;
}

/** Conversion inverse, pour préremplir un formulaire depuis l'API. */
export function centsToEuros(cents: number | null | undefined): number {
  const value = Number(cents);
  return Number.isFinite(value) ? value / 100 : 0;
}
