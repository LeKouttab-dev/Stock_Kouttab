/**
 * Calendrier : lecture des agendas Google, servis par le backend.
 *
 * Le navigateur ne parle jamais à Google — c'est le serveur qui détient le
 * compte de service. Il n'y a donc ni jeton Google ni compte Google à avoir
 * côté bénévole : l'onglet s'affiche pour qui est connecté à l'application.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type {
  Agenda,
  CalendrierReponse,
  EtatCalendrier,
  ReglageAgenda,
  ReglagesAgendas,
  SalleDeduite,
} from '@/types/api';

export const calendarQueryKeys = {
  all: ['calendar'] as const,
  agendas: () => [...calendarQueryKeys.all, 'agendas'] as const,
  evenements: (debut: string, fin: string, agendas?: string[]) =>
    [...calendarQueryKeys.all, 'evenements', debut, fin, agendas ?? 'tous'] as const,
  etat: () => [...calendarQueryKeys.all, 'etat'] as const,
  reglages: () => [...calendarQueryKeys.all, 'reglages-agendas'] as const,
};

async function fetchAgendas(): Promise<Agenda[]> {
  const { data } = await api.get<Agenda[]>('/calendar/agendas');
  return data;
}

export function useAgendas() {
  return useQuery({
    queryKey: calendarQueryKeys.agendas(),
    // La liste des agendas bouge à chaque rentrée, pas à chaque minute.
    staleTime: 10 * 60_000,
    queryFn: fetchAgendas,
  });
}

async function fetchEvenements(
  debut: string,
  fin: string,
  agendas?: string[],
): Promise<CalendrierReponse> {
  const { data } = await api.get<CalendrierReponse>('/calendar', {
    // `agendas` est répété une fois par identifiant : c'est la forme attendue
    // par FastAPI pour une liste en query string.
    params: { debut, fin, agendas },
    paramsSerializer: { indexes: null },
  });
  return data;
}

/**
 * Événements d'une fenêtre.
 *
 * La fenêtre est celle que FullCalendar affiche, arrondie au mois : sans cet
 * arrondi, chaque navigation déclencherait une requête distincte et le cache
 * ne servirait jamais.
 */
export function useEvenements(debut: string | null, fin: string | null, agendas?: string[]) {
  return useQuery({
    queryKey: calendarQueryKeys.evenements(debut ?? '', fin ?? '', agendas),
    enabled: Boolean(debut && fin),
    staleTime: 60_000,
    queryFn: () => fetchEvenements(debut as string, fin as string, agendas),
  });
}

export function useEtatCalendrier(actif = true) {
  return useQuery({
    queryKey: calendarQueryKeys.etat(),
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<EtatCalendrier>('/calendar/etat');
      return data;
    },
  });
}

/** Vide le cache serveur : ce qui vient d'être corrigé dans Google apparaît. */
export function useRafraichirCalendrier() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async () => {
      const { data } = await api.post<EtatCalendrier>('/calendar/rafraichir');
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: calendarQueryKeys.all }),
  });
}

/* ---- Réglages par agenda (Super Admin) --------------------------------- */

export function useReglagesAgendas(actif = true) {
  return useQuery({
    queryKey: calendarQueryKeys.reglages(),
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<ReglagesAgendas>('/calendar/reglages-agendas');
      return data;
    },
  });
}

/**
 * Enregistre un lot de réglages.
 *
 * En lot, et non une requête par ligne : l'écran est un tableau de quarante-
 * cinq agendas, on en règle plusieurs puis on enregistre. Quarante-cinq
 * requêtes vers une base distante coûteraient quarante-cinq allers-retours.
 */
export function useEnregistrerReglagesAgendas() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (reglages: Record<string, Omit<ReglageAgenda, 'agenda_id'>>) => {
      const { data } = await api.put<ReglagesAgendas>('/calendar/reglages-agendas', {
        reglages,
      });
      return data;
    },
    // Les salles changent ce que la grille affiche : tout le calendrier est à
    // relire, pas seulement les réglages.
    onSuccess: () => qc.invalidateQueries({ queryKey: calendarQueryKeys.all }),
  });
}

/**
 * Propose une salle par agenda d'après les réservations Google passées.
 *
 * `enabled: false` : rien ne part tant que personne n'a cliqué. C'est un appel
 * à Google sur soixante jours, pas une donnée d'affichage.
 */
export function useDeduireLesSalles(jours = 60) {
  return useQuery({
    queryKey: [...calendarQueryKeys.reglages(), 'deduire', jours] as const,
    enabled: false,
    gcTime: 0,
    queryFn: async () => {
      const { data } = await api.get<SalleDeduite[]>('/calendar/reglages-agendas/deduire', {
        params: { jours },
      });
      return data;
    },
  });
}
