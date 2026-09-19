/**
 * Règles d'affichage du calendrier, hors composant.
 *
 * Deux pièges de Google Agenda vivent ici : la borne de fin exclusive des
 * journées entières, et des couleurs d'agenda trop claires pour porter du
 * texte blanc.
 */
import type { EvenementCalendrier } from '@/types/api';

/** Couleur de texte lisible sur la pastille colorée d'un agenda. */
export function contrasteSur(fond: string | null | undefined): string {
  if (!fond || !/^#[0-9a-f]{6}$/i.test(fond)) return '#ffffff';
  const r = parseInt(fond.slice(1, 3), 16);
  const g = parseInt(fond.slice(3, 5), 16);
  const b = parseInt(fond.slice(5, 7), 16);
  // Luminance perçue (ITU-R BT.601) : le jaune et le vert clair de Google
  // sont illisibles en blanc.
  return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? '#1f2937' : '#ffffff';
}

/**
 * Tout s'affiche à l'heure de Paris, jamais à celle de l'appareil.
 *
 * C'est le fuseau de tous les agendas de l'association, et celui que la grille
 * du calendrier impose déjà (`timeZone` de FullCalendar). Sans ce réglage, un
 * bénévole en déplacement lisait « 17:00 » dans la grille et « 15:00 » dans la
 * fiche du même cours.
 */
const FUSEAU = 'Europe/Paris';

const JOUR = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: FUSEAU,
});
const HEURE = new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: FUSEAU,
});

const UN_JOUR_MS = 86_400_000;

/** Plage d'un événement, telle qu'elle se lit dans sa fiche. */
export function formatPlage(evenement: EvenementCalendrier): string {
  const debut = new Date(evenement.debut);
  const fin = new Date(evenement.fin);

  if (evenement.journee_entiere) {
    // La borne de fin d'une journée entière est EXCLUSIVE chez Google :
    // affichée telle quelle, une sortie du samedi se lirait « du samedi au
    // dimanche ».
    const finReelle = new Date(fin.getTime() - UN_JOUR_MS);
    return finReelle > debut
      ? `Du ${JOUR.format(debut)} au ${JOUR.format(finReelle)}`
      : `${JOUR.format(debut)} — toute la journée`;
  }

  const memeJour = debut.toDateString() === fin.toDateString();
  return memeJour
    ? `${JOUR.format(debut)}, ${HEURE.format(debut)} – ${HEURE.format(fin)}`
    : `${JOUR.format(debut)} ${HEURE.format(debut)} → ${JOUR.format(fin)} ${HEURE.format(fin)}`;
}
