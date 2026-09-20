import { useEffect, useMemo, useState } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import frLocale from '@fullcalendar/core/locales/fr';
import type { DatesSetArg, EventClickArg, EventInput } from '@fullcalendar/core';
import { AlertTriangle, CalendarDays, History, MapPin, RefreshCw, Repeat, User } from 'lucide-react';

import { Alert } from '@/components/ui/alert';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAgendas, useEvenements, useRafraichirCalendrier } from '@/api/endpoints/calendar';
import { contrasteSur, formatPlage } from '@/lib/calendrier';
import { fr as i18n } from '@/lib/i18n/fr';
import type { EvenementCalendrier } from '@/types/api';

/**
 * Agendas décochés, retenus d'une visite à l'autre.
 *
 * On mémorise ce qui est MASQUÉ, pas ce qui est affiché : un agenda créé à la
 * rentrée apparaît alors de lui-même, alors qu'une liste de cases cochées
 * l'aurait laissé invisible jusqu'à ce que quelqu'un pense à le rétablir.
 */
const CLE_MASQUES = 'calendrier.agendas-masques';

function lireMasques(): string[] {
  try {
    const brut = localStorage.getItem(CLE_MASQUES);
    return brut ? (JSON.parse(brut) as string[]) : [];
  } catch {
    return [];
  }
}

export function CalendarPage() {
  const [fenetre, setFenetre] = useState<{ debut: string; fin: string } | null>(null);
  const [masques, setMasques] = useState<string[]>(lireMasques);
  const [recherche, setRecherche] = useState('');
  const [ouvert, setOuvert] = useState<EvenementCalendrier | null>(null);

  const { data: agendas = [], isLoading: agendasEnCours, error: erreurAgendas } = useAgendas();
  const rafraichir = useRafraichirCalendrier();

  // La fenêtre envoyée au serveur est celle que FullCalendar affiche : il
  // déborde déjà sur les semaines voisines, inutile de l'élargir.
  const {
    data,
    isFetching,
    error: erreurEvenements,
  } = useEvenements(fenetre?.debut ?? null, fenetre?.fin ?? null);

  useEffect(() => {
    try {
      localStorage.setItem(CLE_MASQUES, JSON.stringify(masques));
    } catch {
      // Navigation privée, stockage plein : l'onglet doit fonctionner quand même.
    }
  }, [masques]);

  const visibles = useMemo(
    () => new Set(agendas.filter((a) => !masques.includes(a.id)).map((a) => a.id)),
    [agendas, masques],
  );

  const evenements: EventInput[] = useMemo(
    () =>
      (data?.evenements ?? [])
        .filter((e) => visibles.has(e.agenda_id))
        .map((e) => ({
          id: `${e.agenda_id}::${e.id}`,
          title: e.titre,
          start: e.debut,
          end: e.fin,
          allDay: e.journee_entiere,
          backgroundColor: e.couleur ?? '#3d4f3d',
          borderColor: e.couleur ?? '#3d4f3d',
          textColor: contrasteSur(e.couleur),
          extendedProps: { source: e },
        })),
    [data, visibles],
  );

  const listeAgendas = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    return terme ? agendas.filter((a) => a.nom.toLowerCase().includes(terme)) : agendas;
  }, [agendas, recherche]);

  const basculer = (id: string) =>
    setMasques((actuels) =>
      actuels.includes(id) ? actuels.filter((m) => m !== id) : [...actuels, id],
    );

  const toutAfficher = () => setMasques([]);
  const toutMasquer = () => setMasques(agendas.map((a) => a.id));

  const onDatesSet = (arg: DatesSetArg) => {
    const debut = arg.start.toISOString();
    const fin = arg.end.toISOString();
    setFenetre((precedente) =>
      precedente?.debut === debut && precedente?.fin === fin ? precedente : { debut, fin },
    );
  };

  const onEventClick = (arg: EventClickArg) => {
    // Un événement « liste » est rendu comme un lien : sans cela, le clic
    // ouvrirait Google Agenda dans un onglet au lieu de la fiche.
    arg.jsEvent.preventDefault();
    setOuvert(arg.event.extendedProps.source as EvenementCalendrier);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-bold text-forest">
            {i18n.calendrier.titre}
          </h1>
          <p className="text-sm text-forest/70">{i18n.calendrier.sousTitre}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          // Vider un cache qui ne sert pas encore Google n'apporte rien :
          // le bouton disparaît plutôt que de promettre une mise à jour.
          hidden={data?.instantane}
          disabled={rafraichir.isPending}
          onClick={() => rafraichir.mutate(undefined)}
        >
          <RefreshCw className={`h-4 w-4 ${rafraichir.isPending ? 'animate-spin' : ''}`} />
          {i18n.calendrier.rafraichir}
        </Button>
      </div>

      {/* Le message du serveur, pas un libellé générique : « compte de service
          non renseigné » et « Google injoignable » n'appellent pas le même
          geste, et seul le premier demande un Super Admin. */}
      {(erreurAgendas || erreurEvenements) && (
        <ErrorAlert
          error={erreurAgendas ?? erreurEvenements}
          title={i18n.calendrier.indisponible}
        />
      )}

      {/* Un planning daté qui se présenterait comme le direct ferait manquer
          un cours déplacé : tant que la source est figée, l'écran le dit, et
          il donne la date du relevé. */}
      {data?.instantane && (
        <Alert variant="info">
          <History className="h-4 w-4" />
          <div>
            <p className="font-semibold">{i18n.calendrier.instantaneTitre}</p>
            <p className="text-sm">
              {i18n.calendrier.instantaneTexte.replace(
                '{date}',
                data.genere_le
                  ? new Intl.DateTimeFormat('fr-FR', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      timeZone: 'Europe/Paris',
                    }).format(new Date(`${data.genere_le}T12:00:00+02:00`))
                  : 'ce jour',
              )}
            </p>
          </div>
        </Alert>
      )}

      {/* Un agenda illisible n'efface pas les autres : on le dit, et on sert
          ce qu'on a. */}
      {(data?.agendas_en_erreur?.length ?? 0) > 0 && (
        <Alert variant="warning">
          <AlertTriangle className="h-4 w-4" />
          <span>
            {i18n.calendrier.agendasEnErreur} {data?.agendas_en_erreur.join(', ')}
          </span>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-[17rem_1fr]">
        <Card className="order-2 lg:order-1">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-forest">{i18n.calendrier.mesAgendas}</p>
              <span className="text-xs text-forest/60">
                {visibles.size}/{agendas.length}
              </span>
            </div>

            <Input
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder={i18n.calendrier.chercherAgenda}
              className="h-8 text-sm"
            />

            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={toutAfficher}>
                {i18n.calendrier.toutAfficher}
              </Button>
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={toutMasquer}>
                {i18n.calendrier.toutMasquer}
              </Button>
            </div>

            {agendasEnCours ? (
              <Skeleton className="h-64" />
            ) : (
              <ul className="max-h-[28rem] space-y-1 overflow-y-auto scrollbar-thin pr-1">
                {listeAgendas.map((agenda) => (
                  <li key={agenda.id}>
                    <label className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 hover:bg-cream-100">
                      <Checkbox
                        checked={!masques.includes(agenda.id)}
                        onCheckedChange={() => basculer(agenda.id)}
                        className="mt-0.5"
                        style={{
                          backgroundColor: !masques.includes(agenda.id)
                            ? (agenda.couleur ?? undefined)
                            : undefined,
                          borderColor: agenda.couleur ?? undefined,
                        }}
                      />
                      <span className="flex-1 text-xs leading-snug text-forest">
                        {agenda.nom}
                        {agenda.restreint && (
                          <Badge variant="outline" className="ml-1 px-1 py-0 text-[10px]">
                            {i18n.calendrier.restreint}
                          </Badge>
                        )}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="order-1 lg:order-2">
          <CardContent className="p-2 sm:p-4">
            {isFetching && (
              <p className="pb-2 text-xs text-forest/60">{i18n.calendrier.chargement}</p>
            )}
            <div className="calendrier-kouttab">
              <FullCalendar
                plugins={[dayGridPlugin, timeGridPlugin, listPlugin]}
                initialView="dayGridMonth"
                locale={frLocale}
                timeZone="Europe/Paris"
                headerToolbar={{
                  left: 'prev,next today',
                  center: 'title',
                  right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
                }}
                buttonText={{
                  today: "Aujourd'hui",
                  month: 'Mois',
                  week: 'Semaine',
                  day: 'Jour',
                  list: 'Liste',
                }}
                // Les cours commencent tôt et les soirées finissent tard :
                // une grille 00 h–24 h obligerait à faire défiler pour rien.
                slotMinTime="07:00:00"
                slotMaxTime="23:00:00"
                scrollTime="08:00:00"
                nowIndicator
                weekNumbers={false}
                firstDay={1}
                height="auto"
                dayMaxEvents={4}
                events={evenements}
                datesSet={onDatesSet}
                eventClick={onEventClick}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(ouvert)} onOpenChange={(o) => !o && setOuvert(null)}>
        <DialogContent>
          {ouvert && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-6 font-serif text-lg text-forest">
                  {ouvert.titre}
                </DialogTitle>
                <DialogDescription className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: ouvert.couleur ?? '#3d4f3d' }}
                  />
                  {ouvert.agenda_nom}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-sm text-forest">
                <p className="flex items-start gap-2">
                  <CalendarDays className="mt-0.5 h-4 w-4 flex-shrink-0 text-terracotta" />
                  <span>{formatPlage(ouvert)}</span>
                </p>
                {ouvert.lieu && (
                  <p className="flex items-start gap-2">
                    <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-terracotta" />
                    <span>{ouvert.lieu}</span>
                  </p>
                )}
                {ouvert.organisateur && (
                  <p className="flex items-start gap-2">
                    <User className="mt-0.5 h-4 w-4 flex-shrink-0 text-terracotta" />
                    <span>{ouvert.organisateur}</span>
                  </p>
                )}
                {ouvert.recurrent && (
                  <p className="flex items-center gap-2 text-xs text-forest/70">
                    <Repeat className="h-3.5 w-3.5" />
                    {i18n.calendrier.recurrent}
                  </p>
                )}
                {ouvert.description && (
                  // Le texte de Google peut contenir du HTML ; on l'affiche
                  // en brut plutôt que de l'injecter dans la page.
                  <p className="whitespace-pre-wrap rounded bg-cream-100 p-3 text-xs leading-relaxed">
                    {ouvert.description}
                  </p>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
