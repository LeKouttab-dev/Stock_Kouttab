import { contrasteSur } from '@/lib/calendrier';
import { enHeure, type BlocGrille } from '@/lib/calendrier-grille';
import { cn } from '@/lib/utils';

const COULEUR_DEFAUT = '#3d4f3d';

/** Hauteur d'une ligne de texte de la carte (11 px, interligne serré). */
const LIGNE = 14;
/** Marge haute de la carte. */
const MARGE_HAUT = 4;

interface CarteSeanceProps {
  bloc: BlocGrille;
  hauteur: number;
  /** Largeur occupée, en % de la colonne. */
  largeur: number;
  /** Posée par-dessus un cours (créneau court) : liseré pour s'en détacher. */
  posee?: boolean;
  /** Hauteur couverte en haut par des créneaux posés : le texte commence dessous. */
  retraitHaut?: number;
  onOuvrir: (bloc: BlocGrille) => void;
}

/**
 * Une séance dans la grille.
 *
 * ```
 * Éducation islamique
 * 6-11ans
 * U. Soundousse
 * 19            17:30–19:30
 * ```
 *
 * **Tout en haut, groupé.** Le titre en entier, sur autant de lignes que la
 * hauteur en permet, puis l'enseignant, puis le numéro et l'horaire juste
 * dessous. Ancrer cette dernière ligne tout en bas l'éloignait du titre de
 * toute la hauteur du cours, et l'œil devait parcourir la carte pour relier
 * les deux.
 *
 * **Le texte commence sous ce qui est posé dessus.** Un rendez-vous posé en
 * haut d'un cours en masquait le titre ; `retraitHaut` décale le texte d'autant.
 *
 * **Le nom part en dernier.** Quand la place manque, on sacrifie l'enseignant,
 * puis la ligne du bas, jamais le nom : une carte réduite à « 19 18:30 » ne dit
 * rien de ce qui se passe dans la salle.
 *
 * **Une salle devinée se voit.** Quand elle ne vient pas d'une réservation
 * Google — habitude de l'agenda ou Maziri par défaut —, la carte porte une
 * bordure gauche en pointillés et le dit dans son nom accessible.
 */
export function CarteSeance({
  bloc,
  hauteur,
  largeur,
  posee = false,
  retraitHaut = 0,
  onOuvrir,
}: CarteSeanceProps) {
  const premier = bloc.evenements[0];
  const plage = bloc.evenements.length > 1;
  const fond = premier.couleur ?? COULEUR_DEFAUT;
  const encre = contrasteSur(premier.couleur);

  const devinee = premier.salle_source !== 'google';
  const precision =
    premier.salle_source === 'correspondance'
      ? ' (salle habituelle, non réservée dans Google)'
      : premier.salle_source === 'defaut'
        ? ' (par défaut, aucune salle renseignée)'
        : '';

  const titre = plage
    ? premier.nom_court || premier.agenda_nom
    : premier.nom_court || premier.titre;

  // Une demi-colonne n'a pas la place d'un horaire complet ni d'un nom
  // d'enseignant : on y garde l'heure de début seule.
  const etroite = largeur < 60;
  // La place réellement disponible pour le texte, sous ce qui est posé dessus.
  // Sans place pour le titre, on ne décale pas : mieux vaut un titre à moitié
  // couvert qu'aucun titre.
  const decalage = hauteur - retraitHaut >= 30 ? retraitHaut : 0;
  const utile = hauteur - decalage;
  const avecBas = utile >= 30;
  const avecEnseignant = !etroite && !plage && Boolean(premier.enseignant) && utile >= 44 + LIGNE;
  const lignesTitre = Math.max(
    1,
    Math.floor(
      (utile - MARGE_HAUT - (avecBas ? LIGNE : 0) - (avecEnseignant ? LIGNE : 0)) / LIGNE,
    ),
  );

  const numero = plage ? `×${bloc.evenements.length}` : premier.numero;
  const horaire = etroite
    ? enHeure(bloc.debutMinutes)
    : `${enHeure(bloc.debutMinutes)}–${enHeure(bloc.finMinutes)}`;

  const description = [
    plage
      ? `${premier.agenda_nom}, ${bloc.evenements.length} créneaux`
      : `${premier.agenda_nom}${premier.numero ? `, séance ${premier.numero}` : ''}`,
    premier.enseignant,
    premier.salle_libelle && `${premier.salle_libelle}${precision}`,
    `de ${enHeure(bloc.debutMinutes)} à ${enHeure(bloc.finMinutes)}`,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <button
      type="button"
      onClick={() => onOuvrir(bloc)}
      // Le nom accessible porte la vérité entière : la carte visible est
      // tronquée, pas ce que lit un lecteur d'écran.
      aria-label={description}
      title={description}
      className={cn(
        'flex w-full flex-col overflow-hidden rounded px-1 pb-0.5 text-left text-[11px] leading-tight',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1',
        devinee && 'border-l-2 border-dashed',
        // Posée sur un cours : le liseré blanc la détache de la carte dessous.
        posee && 'shadow-sm ring-1 ring-white',
      )}
      style={{
        backgroundColor: fond,
        color: encre,
        borderLeftColor: devinee ? encre : undefined,
        height: `${hauteur}px`,
        paddingTop: MARGE_HAUT + decalage,
      }}
    >
      <span
        className={cn('font-semibold', lignesTitre === 1 ? 'truncate' : 'break-words')}
        style={
          lignesTitre > 1
            ? {
                display: '-webkit-box',
                WebkitLineClamp: lignesTitre,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }
            : undefined
        }
      >
        {titre}
      </span>

      {avecEnseignant && <span className="truncate opacity-90">{premier.enseignant}</span>}

      {avecBas && (
        <span className="mt-0.5 flex items-baseline justify-between gap-1 opacity-80">
          <span className="shrink-0 tabular-nums">{numero}</span>
          <span className="truncate tabular-nums">{horaire}</span>
        </span>
      )}
    </button>
  );
}
