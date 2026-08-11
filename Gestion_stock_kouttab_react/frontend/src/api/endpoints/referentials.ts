/**
 * Référentiels comptables : pôles et événements.
 *
 * Regroupés dans un seul module parce qu'ils sont toujours consommés ensemble
 * par le formulaire de dépôt.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { AppEvent, EventSyncResult, Pole } from '@/types/api';

export const poleQueryKeys = {
  all: ['poles'] as const,
  list: (includeInactive?: boolean) => [...poleQueryKeys.all, { includeInactive }] as const,
};

export const eventQueryKeys = {
  all: ['events'] as const,
  list: (includeInactive?: boolean) => [...eventQueryKeys.all, { includeInactive }] as const,
};

/* ---- Pôles ------------------------------------------------------------- */

async function fetchPoles(includeInactive = false): Promise<Pole[]> {
  const { data } = await api.get<Pole[]>('/poles', {
    params: includeInactive ? { include_inactive: true } : undefined,
  });
  return data;
}

export function usePoles(includeInactive = false) {
  return useQuery({
    queryKey: poleQueryKeys.list(includeInactive),
    queryFn: () => fetchPoles(includeInactive),
  });
}

export function useCreatePole() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (payload: { nom: string; ordre?: number }) => {
      const { data } = await api.post<Pole>('/poles', payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: poleQueryKeys.all }),
  });
}

export function useUpdatePole() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (params: {
      id: number;
      nom?: string;
      is_active?: boolean;
      ordre?: number;
    }) => {
      const { id, ...body } = params;
      const { data } = await api.patch<Pole>(`/poles/${id}`, body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: poleQueryKeys.all }),
  });
}

export function useDeletePole() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/poles/${id}`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: poleQueryKeys.all }),
  });
}

/* ---- Événements -------------------------------------------------------- */

async function fetchEvents(includeInactive = false): Promise<AppEvent[]> {
  const { data } = await api.get<AppEvent[]>('/events', {
    params: includeInactive ? { include_inactive: true } : undefined,
  });
  return data;
}

export function useEvents(includeInactive = false) {
  return useQuery({
    queryKey: eventQueryKeys.list(includeInactive),
    queryFn: () => fetchEvents(includeInactive),
  });
}

export function useSyncEvents() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async () => {
      const { data } = await api.post<EventSyncResult>('/events/sync');
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: eventQueryKeys.all }),
  });
}

export function useCreateEvent() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (payload: { nom: string; date_evenement?: string | null }) => {
      const { data } = await api.post<AppEvent>('/events', payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: eventQueryKeys.all }),
  });
}

export function useUpdateEvent() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (params: {
      id: number;
      nom?: string;
      date_evenement?: string | null;
      is_active?: boolean;
    }) => {
      const { id, ...body } = params;
      const { data } = await api.patch<AppEvent>(`/events/${id}`, body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: eventQueryKeys.all }),
  });
}

export function useDeleteEvent() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/events/${id}`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: eventQueryKeys.all }),
  });
}
