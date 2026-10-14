import { useEffect, useMemo, useState } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import frLocale from '@fullcalendar/core/locales/fr';
import type { DatesSetArg, EventClickArg, EventInput } from '@fullcalendar/core';
import { History } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { BarreCalendrier } from '@/components/calendrier/BarreCalendrier';
import { FicheEvenement } from '@/components/calendrier/FicheEvenement';
import { GrilleSalles } from '@/components/calendrier/GrilleSalles';
import { PanneauFiltres } from '@/components/calendrier/PanneauFiltres';
import { useAgendas, useEvenements, useRafraichirCalendrier } from '@/api/endpoints/calendar';
import {
  JOURS_PAR_VUE,
  useCalendrierVue,
  useMaintenant,
  useSallesMasquees,
} from '@/hooks/useCalendrierVue';
import { contrasteSur } from '@/lib/calendrier';
import { joursDeLaVue, type BlocGrille } from '@/lib/calendrier-grille';
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
const CLE_PAR_SALLE = 'calendrier.par-salle';

function lireMasques(): string[] {
  try {
    const brut = localStorage.getItem(CLE_MASQUES);
    return brut ? (JSON.parse(brut) as string[]) : [];
  } catch {
    return [];
  }
}

const PERIODE = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Paris',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
});

/**
 * L'emploi du temps de l'institut.
 *
 * Cinq vues : **Mois** et **Liste** sont rendues par FullCalendar, **Semaine**,
 * **3 jours** et **Jour** par la grille maison — les colonnes par salle
 * appartiennent à FullCalendar Premium, sous licence payante, et le rendu des
 * cartes demandait de toute façon du sur-mesure.
 *
 * La page ne porte que l'état et l'assemblage : le calcul est dans
 * `lib/calendrier-grille.ts`, l'affichage dans `components/calendrier/`.
 */
export function CalendarPage() {
  const [fenetre, setFenetre] = useState<{ debut: string; fin: string } | null>(null);
  const [masques, setMasques] = useState<string[]>(lireMasques);
  const [recherche, setRecherche] = useState('');
  const [ouvert, setOuvert] = useState<BlocGrille | null>(null);
  const [panneauOuvert, setPanneauOuvert] = useState(true);
  const [parSalle, setParSalle] = useState(() => {
    try {
      return localStorage.getItem(CLE_PAR_SALLE) !== 'non';
    } catch {
      return true;
    }
  });

  const { vue, choisie, choisir, ancre, decaler, aujourdhui } = useCalendrierVue();
  const { masquees: sallesMasquees, basculer: basculerSalle } = useSallesMasquees();
  const maintenant = useMaintenant();

  const { data: agendas = [], isLoading: agendasEnCours, error: erreurAgendas } = useAgendas();
  const rafraichir = useRafraichirCalendrier();

  const grille = vue !== 'mois' && vue !== 'liste';
  const jours = useMemo(
    () => (grille ? joursDeLaVue(ancre, JOURS_PAR_VUE[vue] ?? 7) : []),
    [grille, ancre, vue],
  );

  // Pour les vues de grille, la fenêtre est calculée ici ; pour Mois et Liste,
  // c'est FullCalendar qui l'annonce par `datesSet`.
  useEffect(() => {
    if (!grille || !jours.length) return;
    const debut = new Date(`${jours[0]}T00:00:00`).toISOString();
    const finJour = new Date(`${jours[jours.length - 1]}T00:00:00`);
    finJour.setDate(finJour.getDate() + 1);
    const fin = finJour.toISOString();
    setFenetre((precedente) =>
      precedente?.debut === debut && precedente?.fin === fin ? precedente : { debut, fin },
    );
  }, [grille, jours]);

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

  const evenements = useMemo(
    () => (data?.evenements ?? []).filter((e) => visibles.has(e.agenda_id)),
    [data, visibles],
  );

  const salles = data?.salles ?? {};
  const sallesVisibles = useMemo(
    () => Object.keys(salles).filter((cle) => !sallesMasquees.includes(cle)),
    [salles, sallesMasquees],
  );

  const pourFullCalendar: EventInput[] = useMemo(
    () =>
      evenements.map((e) => ({
        id: `${e.agenda_id}::${e.id}`,
        // Le titre Google est « cours 19 » : c'est le nom d'agenda raccourci
        // qui porte le sens, dans le mois comme dans la grille.
        // Un cours se lit par son agenda (« Coran ENF 1 · 19 ») ; ce qui n'est
        // pas un cours — un atelier, un rendez-vous — par son propre titre.
        title: e.numero ? `${e.nom_court} · ${e.numero}` : e.titre,
        start: e.debut,
        end: e.fin,
        allDay: e.journee_entiere,
        backgroundColor: e.couleur ?? '#3d4f3d',
        borderColor: e.couleur ?? '#3d4f3d',
        textColor: contrasteSur(e.couleur),
        extendedProps: { source: e },
      })),
    [evenements],
  );

  const basculerParSalle = () => {
    const suivant = !parSalle;
    setParSalle(suivant);
    try {
      localStorage.setItem(CLE_PAR_SALLE, suivant ? 'oui' : 'non');
    } catch {
      /* sans effet */
    }
  };

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
    const source = arg.event.extendedProps.source as EvenementCalendrier;
    setOuvert({
      cle: source.id,
      evenements: [source],
      debutMinutes: 0,
      finMinutes: 0,
      jour: '',
    });
  };

  const titre = grille
    ? jours.length === 1
      ? PERIODE.format(new Date(`${jours[0]}T12:00:00`))
      : `${PERIODE.format(new Date(`${jours[0]}T12:00:00`))} — ${PERIODE.format(
          new Date(`${jours[jours.length - 1]}T12:00:00`),
        )}`
    : PERIODE.format(ancre);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <BarreCalendrier
        vue={vue}
        choisie={choisie}
        titre={titre}
        parSalle={parSalle}
        panneauOuvert={panneauOuvert}
        rafraichissement={rafraichir.isPending || isFetching}
        onVue={choisir}
        onDecaler={decaler}
        onAujourdhui={aujourdhui}
        onParSalle={basculerParSalle}
        onPanneau={() => setPanneauOuvert((o) => !o)}
        onRafraichir={data?.instantane ? undefined : () => rafraichir.mutate(undefined)}
      />

      {(erreurAgendas || erreurEvenements) && (
        <div className="px-3 pt-2">
          <ErrorAlert error={erreurAgendas ?? erreurEvenements} />
        </div>
      )}

      {data?.instantane && (
        <div className="px-3 pt-2">
          <Alert variant="info">
            <History className="h-4 w-4" />
            <AlertDescription>
              <span className="font-semibold">{i18n.calendrier.instantaneTitre}</span>{' '}
              {i18n.calendrier.instantaneTexte.replace('{date}', data.genere_le ?? 'ce jour')}
            </AlertDescription>
          </Alert>
        </div>
      )}

      {(data?.agendas_en_erreur?.length ?? 0) > 0 && (
        <div className="px-3 pt-2">
          <Alert variant="warning">
            <AlertDescription>
              Agendas injoignables : {data?.agendas_en_erreur.join(', ')}
            </AlertDescription>
          </Alert>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {panneauOuvert && (
          <PanneauFiltres
            agendas={agendas}
            chargement={agendasEnCours}
            recherche={recherche}
            masques={masques}
            salles={salles}
            sallesMasquees={sallesMasquees}
            parSalle={parSalle && grille}
            onRecherche={setRecherche}
            onReglerAgendas={(ids, afficher) =>
              setMasques((actuels) =>
                afficher
                  ? actuels.filter((m) => !ids.includes(m))
                  : [...new Set([...actuels, ...ids])],
              )
            }
            onBasculerSalle={basculerSalle}
          />
        )}

        {grille ? (
          <GrilleSalles
            jours={jours}
            evenements={evenements}
            salles={salles}
            sallesVisibles={sallesVisibles}
            parSalle={parSalle}
            maintenant={maintenant}
            onOuvrir={setOuvert}
          />
        ) : (
          <div className="calendrier-kouttab min-h-0 flex-1 overflow-y-auto p-3">
            <FullCalendar
              plugins={[dayGridPlugin, listPlugin]}
              initialView={vue === 'mois' ? 'dayGridMonth' : 'listWeek'}
              // FullCalendar ne relit `initialDate` qu'au montage : sans la date
              // dans la clé, les flèches précédent / suivant ne faisaient rien
              // en vues Mois et Liste.
              key={`${vue}-${ancre.toISOString().slice(0, 10)}`}
              locale={frLocale}
              timeZone="Europe/Paris"
              headerToolbar={false}
              initialDate={ancre}
              firstDay={1}
              height="auto"
              dayMaxEvents={4}
              events={pourFullCalendar}
              datesSet={onDatesSet}
              eventClick={onEventClick}
            />
          </div>
        )}
      </div>

      <FicheEvenement bloc={ouvert} onFermer={() => setOuvert(null)} />
    </div>
  );
}
