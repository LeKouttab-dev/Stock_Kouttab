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
import type { Agenda, CalendrierReponse, EtatCalendrier } from '@/types/api';

export const calendarQueryKeys = {
  all: ['calendar'] as const,
  agendas: () => [...calendarQueryKeys.all, 'agendas'] as const,
  evenements: (debut: string, fin: string, agendas?: string[]) =>
    [...calendarQueryKeys.all, 'evenements', debut, fin, agendas ?? 'tous'] as const,
  etat: () => [...calendarQueryKeys.all, 'etat'] as const,
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
