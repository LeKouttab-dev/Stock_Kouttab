import { useState } from 'react';
import { CalendarDays, Eye, EyeOff, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  useCreateEvent,
  useDeleteEvent,
  useEvents,
  useSyncEvents,
  useUpdateEvent,
} from '@/api/endpoints/referentials';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Référentiel des événements proposé au dépôt des pièces comptables.
 *
 * Alimenté par synchronisation HelloAsso, complété manuellement pour ce qui n'y
 * figure pas. La synchronisation ne touche jamais aux événements manuels.
 */
export function EventsManagementSection() {
  const { data: events = [], isLoading } = useEvents(true);
  const sync = useSyncEvents();
  const create = useCreateEvent();
  const update = useUpdateEvent();
  const remove = useDeleteEvent();
  const toast = useToast();

  const [newName, setNewName] = useState('');
  const [newDate, setNewDate] = useState('');

  const handleSync = () => {
    sync.mutate(undefined, {
      onSuccess: (result) =>
        toast.success(
          fr.events.syncSucces,
          `${result.created} créé(s), ${result.updated} mis à jour, ${result.skipped} ignoré(s)`,
        ),
    });
  };

  const handleAdd = () => {
    if (!newName.trim()) return;
    create.mutate(
      { nom: newName.trim(), date_evenement: newDate || null },
      {
        onSuccess: () => {
          setNewName('');
          setNewDate('');
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4" aria-hidden />
              {fr.events.title}
            </CardTitle>
            <p className="text-xs text-muted-foreground">{fr.events.subtitle}</p>
          </div>
          <Button variant="outline" onClick={handleSync} loading={sync.isPending}>
            <RefreshCw className="h-4 w-4" />
            {fr.events.synchroniser}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            placeholder={fr.events.nom}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Input
            type="date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
            className="sm:w-48"
          />
          <Button onClick={handleAdd} loading={create.isPending}>
            <Plus className="h-4 w-4" />
            {fr.events.ajouter}
          </Button>
        </div>

        {isLoading ? (
          <Skeleton className="h-32" />
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">{fr.events.aucun}</p>
        ) : (
          <ul className="space-y-1">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2"
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{event.nom}</span>
                  {event.date_evenement && (
                    <span className="text-xs text-muted-foreground">{event.date_evenement}</span>
                  )}
                  <Badge variant={event.source === 'manuel' ? 'secondary' : 'outline'}>
                    {event.source === 'manuel' ? fr.events.manuel : fr.events.helloasso}
                  </Badge>
                  {!event.is_active && <Badge variant="outline">{fr.poles.inactif}</Badge>}
                </span>
                <div className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => update.mutate({ id: event.id, is_active: !event.is_active })}
                    aria-label={event.is_active ? fr.poles.desactiver : fr.poles.activer}
                    title={event.is_active ? fr.poles.desactiver : fr.poles.activer}
                  >
                    {event.is_active ? (
                      <Eye className="h-4 w-4" />
                    ) : (
                      <EyeOff className="h-4 w-4 text-muted-foreground" />
                    )}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => remove.mutate(event.id)}
                    aria-label={fr.poles.supprimer}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
