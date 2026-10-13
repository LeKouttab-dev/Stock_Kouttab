import { CalendarDays, DoorOpen, MapPin, Repeat, User } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { formatPlage } from '@/lib/calendrier';
import { enHeure, type BlocGrille } from '@/lib/calendrier-grille';
import { fr as i18n } from '@/lib/i18n/fr';
import type { EvenementCalendrier } from '@/types/api';

interface FicheEvenementProps {
  bloc: BlocGrille | null;
  onFermer: () => void;
}

function Ligne({ icone: Icone, children }: { icone: typeof MapPin; children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-2">
      <Icone className="mt-0.5 h-4 w-4 flex-shrink-0 text-terracotta" />
      <span>{children}</span>
    </p>
  );
}

function Detail({ evenement }: { evenement: EvenementCalendrier }) {
  const devinee = evenement.salle_source === 'correspondance';
  return (
    <div className="space-y-3 text-sm text-forest">
      <Ligne icone={CalendarDays}>{formatPlage(evenement)}</Ligne>

      {evenement.salle_libelle && (
        <Ligne icone={DoorOpen}>
          {evenement.salle_libelle}
          {devinee && (
            // La distinction porte : une habitude n'est pas une réservation,
            // et quelqu'un qui s'y fie doit savoir que la salle peut être prise.
            <span className="block text-xs text-forest/60">
              Salle habituelle — non réservée dans Google.
            </span>
          )}
        </Ligne>
      )}

      {evenement.lieu && <Ligne icone={MapPin}>{evenement.lieu}</Ligne>}
      {evenement.organisateur && <Ligne icone={User}>{evenement.organisateur}</Ligne>}

      {evenement.recurrent && (
        <p className="flex items-center gap-2 text-xs text-forest/70">
          <Repeat className="h-3.5 w-3.5" />
          {i18n.calendrier.recurrent}
        </p>
      )}

      {evenement.description && (
        // Le texte de Google peut contenir du HTML ; on l'affiche en brut
        // plutôt que de l'injecter dans la page.
        <p className="whitespace-pre-wrap rounded bg-cream-100 p-3 text-xs leading-relaxed">
          {evenement.description}
        </p>
      )}
    </div>
  );
}

/**
 * Le détail d'une séance, ou d'une plage de rendez-vous.
 *
 * Une plage — les permanences administratives, fusionnées dans la grille en un
 * seul bloc — s'ouvre sur la liste de ses créneaux : c'est là que le détail
 * que la carte ne pouvait pas montrer redevient lisible.
 */
export function FicheEvenement({ bloc, onFermer }: FicheEvenementProps) {
  const premier = bloc?.evenements[0];
  const plage = (bloc?.evenements.length ?? 0) > 1;

  return (
    <Dialog open={Boolean(bloc)} onOpenChange={(ouvert) => !ouvert && onFermer()}>
      <DialogContent>
        {bloc && premier && (
          <>
            <DialogHeader>
              <DialogTitle className="pr-6 font-serif text-lg text-forest">
                {plage ? premier.agenda_nom : premier.titre}
              </DialogTitle>
              <DialogDescription className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: premier.couleur ?? '#3d4f3d' }}
                />
                {plage
                  ? `${bloc.evenements.length} créneaux, de ${enHeure(bloc.debutMinutes)} à ${enHeure(bloc.finMinutes)}`
                  : premier.agenda_nom}
              </DialogDescription>
            </DialogHeader>

            {plage ? (
              <ul className="max-h-apercu space-y-1 overflow-y-auto scrollbar-thin text-sm">
                {bloc.evenements.map((evenement) => (
                  <li
                    key={evenement.id}
                    className="flex gap-3 rounded px-2 py-1 odd:bg-cream-100"
                  >
                    <span className="shrink-0 tabular-nums text-forest/70">
                      {formatPlage(evenement).split(', ').pop()}
                    </span>
                    <span className="truncate">{evenement.titre}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Detail evenement={premier} />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
