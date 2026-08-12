import { useEffect, useMemo } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { useEvents } from '@/api/endpoints/referentials';
import { fr } from '@/lib/i18n/fr';

/** Valeur sentinelle : l'événement n'est pas dans la liste. */
export const FREE_EVENT = '__autre__';

interface EventSelectProps {
  /** Identifiant de l'événement choisi dans le référentiel, sinon `null`. */
  eventId: number | null;
  /** Libellé saisi à la main lorsque l'événement n'est pas référencé. */
  freeText: string;
  onEventIdChange: (id: number | null) => void;
  onFreeTextChange: (value: string) => void;
  /** Appelé avec la date de l'événement sélectionné, pour pré-remplir le champ. */
  onEventDate?: (date: string | null) => void;
  /**
   * Famille d'événements du pôle choisi (« T », « G », « J »).
   *
   * Les pôles EV sont déclinés par famille : sous EV(T), proposer les
   * événements de EV(G) n'a pas de sens. `undefined` ou `null` = aucun filtre.
   */
  typeEvenement?: string | null;
  disabled?: boolean;
}

/**
 * Sélecteur d'événement avec repli en saisie libre.
 *
 * La liste vient d'une synchronisation HelloAsso, mais toutes les dépenses ne
 * s'y rattachent pas : une facture d'électricité ou un achat courant n'a aucun
 * événement associé. La saisie libre est donc un cas normal, pas une panne — et
 * elle sert aussi de filet si HelloAsso est indisponible.
 */
export function EventSelect({
  eventId,
  freeText,
  onEventIdChange,
  onFreeTextChange,
  onEventDate,
  typeEvenement,
  disabled,
}: EventSelectProps) {
  const { data: events, isLoading, isError } = useEvents();

  const value = eventId !== null ? String(eventId) : freeText ? FREE_EVENT : '';

  /**
   * Événements proposés : ceux de la famille demandée, **et ceux qui n'en ont
   * aucune**.
   *
   * La famille se renseigne à la main — HelloAsso ne la connaît pas. Filtrer
   * strictement viderait donc la liste au lendemain d'une synchronisation,
   * chaque événement importé arrivant non classé. Les non classés restent
   * visibles jusqu'à ce qu'on les range.
   */
  const proposes = useMemo(() => {
    if (!events) return [];
    if (!typeEvenement) return events;
    return events.filter((e) => !e.type_ev || e.type_ev === typeEvenement);
  }, [events, typeEvenement]);

  const selected = useMemo(() => events?.find((e) => e.id === eventId) ?? null, [events, eventId]);

  // Pré-remplit la date d'événement à la sélection : c'est presque toujours la
  // bonne, et elle reste modifiable.
  useEffect(() => {
    if (selected && onEventDate) onEventDate(selected.date_evenement ?? null);
  }, [selected, onEventDate]);

  const handleChange = (next: string) => {
    if (next === FREE_EVENT) {
      onEventIdChange(null);
      onFreeTextChange(freeText || '');
      return;
    }
    onEventIdChange(Number(next));
    onFreeTextChange('');
  };

  return (
    <div className="space-y-2">
      <Select value={value} onValueChange={handleChange} disabled={disabled || isLoading}>
        <SelectTrigger>
          <SelectValue placeholder={fr.events.selectPlaceholder} />
        </SelectTrigger>
        <SelectContent>
          {/* La saisie libre est proposée EN TÊTE, pas en fin de liste : elle y
              était invisible dès que le référentiel comptait quelques
              événements, et les déposants concluaient que le leur ne pouvait
              pas être saisi. C'est pourtant le cas le plus courant. */}
          <SelectItem value={FREE_EVENT}>{fr.events.notListed}</SelectItem>
          {proposes.map((event) => (
            <SelectItem key={event.id} value={String(event.id)}>
              {event.nom}
              {event.date_evenement ? ` — ${event.date_evenement}` : ''}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Le référentiel est indisponible : on bascule d'office en saisie libre
          plutôt que de bloquer le dépôt. */}
      {isError && <p className="text-xs text-muted-foreground">{fr.events.unavailable}</p>}

      {(value === FREE_EVENT || isError) && (
        <Input
          value={freeText}
          onChange={(e) => onFreeTextChange(e.target.value)}
          placeholder={fr.events.freeTextPlaceholder}
          disabled={disabled}
        />
      )}
    </div>
  );
}
