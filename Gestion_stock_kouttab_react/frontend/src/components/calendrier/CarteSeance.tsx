import { contrasteSur } from '@/lib/calendrier';
import { enHeure, type BlocGrille } from '@/lib/calendrier-grille';
import { cn } from '@/lib/utils';

const COULEUR_DEFAUT = '#3d4f3d';

interface CarteSeanceProps {
  bloc: BlocGrille;
  hauteur: number;
  voies: number;
  onOuvrir: (bloc: BlocGrille) => void;
}

/**
 * Une séance dans la grille.
 *
 * ```
 * Coran ENF 1        №19
 * U. Soundousse
 *               17:30–18:30
 * ```
 *
 * Le titre Google d'un cours est `cours 19` : c'est le **nom d'agenda
 * raccourci** qui porte le sens, et c'est lui qu'on met en tête.
 *
 * **La densité suit la hauteur réelle, pas la vue.** Une colonne large en vue
 * Jour et une colonne étroite en vue Semaine n'ont pas la même place, et un
 * créneau de trente minutes n'a pas celle d'un cours d'une heure. Rien ne doit
 * jamais déborder de la carte.
 *
 * **Une salle devinée se voit.** Quand elle vient de la correspondance saisie
 * dans l'application et non d'une réservation Google, la carte porte une
 * bordure gauche en pointillés et le dit dans son nom accessible : les trois
 * quarts des cours sont dans ce cas, et les présenter comme des réservations
 * enverrait quelqu'un devant une porte occupée.
 */
export function CarteSeance({ bloc, hauteur, voies, onOuvrir }: CarteSeanceProps) {
  const premier = bloc.evenements[0];
  const plage = bloc.evenements.length > 1;
  const fond = premier.couleur ?? COULEUR_DEFAUT;
  const encre = contrasteSur(premier.couleur);

  const horaire = `${enHeure(bloc.debutMinutes)}–${enHeure(bloc.finMinutes)}`;
  // Tout ce qui n'est pas réservé dans Google est une supposition, et se voit
  // comme telle : la salle habituelle de l'agenda, ou Maziri par défaut.
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

  // Trois paliers : tout, l'essentiel, le strict minimum.
  //
  // **Le nom part en dernier.** Une carte réduite à « №19 18:30 » ne dit rien
  // de ce qui se passe dans la salle ; le numéro de séance et l'horaire, eux,
  // se retrouvent au clic. L'ordre de sacrifice est donc l'inverse de l'ordre
  // de lecture : l'horaire, puis l'enseignant, puis le numéro, jamais le nom.
  const large = hauteur >= 44 && voies === 1;
  const moyen = hauteur >= 30 && voies === 1;

  const description = [
    plage
      ? `${premier.agenda_nom}, ${bloc.evenements.length} créneaux`
      : `${premier.agenda_nom}${premier.numero ? `, séance ${premier.numero}` : ''}`,
    premier.enseignant,
    premier.salle_libelle &&
      `${premier.salle_libelle}${precision}`,
    `de ${enHeure(bloc.debutMinutes)} à ${enHeure(bloc.finMinutes)}`,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <button
      type="button"
      onClick={() => onOuvrir(bloc)}
      // Le nom accessible porte la vérité entière : la carte visible est
      // tronquée sur trois lignes, pas ce que lit un lecteur d'écran.
      aria-label={description}
      title={description}
      className={cn(
        'block w-full overflow-hidden rounded px-1 py-0.5 text-left text-[11px] leading-tight',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1',
        devinee && 'border-l-2 border-dashed',
      )}
      style={{
        backgroundColor: fond,
        color: encre,
        borderLeftColor: devinee ? encre : undefined,
        height: `${hauteur}px`,
      }}
    >
      <span className="flex items-baseline justify-between gap-1">
        <span className="min-w-0 flex-1 truncate font-semibold">{titre}</span>
        {plage && <span className="shrink-0 opacity-80">×{bloc.evenements.length}</span>}
        {premier.numero && !plage && moyen && (
          <span className="shrink-0 opacity-80">№{premier.numero}</span>
        )}
        {!large && moyen && (
          <span className="shrink-0 opacity-80">{enHeure(bloc.debutMinutes)}</span>
        )}
      </span>

      {large && premier.enseignant && (
        <span className="block truncate opacity-90">{premier.enseignant}</span>
      )}
      {large && <span className="block text-right opacity-80">{horaire}</span>}
    </button>
  );
}
