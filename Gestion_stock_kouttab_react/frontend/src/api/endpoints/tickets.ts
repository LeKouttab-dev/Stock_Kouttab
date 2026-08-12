/**
 * Tickets de justificatif : ce que la comptabilité réclame aux bénévoles.
 *
 * Deux vues du même objet : la comptabilité voit tous les tickets et les gère,
 * chacun voit ceux qui le concernent. Le serveur filtre — le front n'a rien à
 * masquer.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import { notificationQueryKeys } from './notifications';
import type { JustificatifTicket } from '@/types/api';

export const ticketQueryKeys = {
  all: ['tickets'] as const,
  list: (statut?: string) => [...ticketQueryKeys.all, 'list', { statut }] as const,
  mine: () => [...ticketQueryKeys.all, 'mine'] as const,
};

export interface CreateTicketPayload {
  id_user: number;
  libelle: string;
  description?: string;
  montant_attendu?: string;
  date_achat?: string;
  fournisseur?: string;
}

export function useTickets(statut?: string) {
  return useQuery({
    queryKey: ticketQueryKeys.list(statut),
    queryFn: async () => {
      const { data } = await api.get<JustificatifTicket[]>('/tickets', {
        params: statut ? { statut } : undefined,
      });
      return data;
    },
  });
}

export function useMyTickets() {
  return useQuery({
    queryKey: ticketQueryKeys.mine(),
    queryFn: async () => {
      const { data } = await api.get<JustificatifTicket[]>('/tickets/me');
      return data;
    },
  });
}

/** Invalide les listes ET les compteurs : un ticket change les deux. */
function useTicketMutation<TVars, TData>(fn: (vars: TVars) => Promise<TData>) {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ticketQueryKeys.all });
      qc.invalidateQueries({ queryKey: notificationQueryKeys.all });
    },
  });
}

export function useCreateTicket() {
  return useTicketMutation(async (payload: CreateTicketPayload) => {
    const { data } = await api.post<JustificatifTicket>('/tickets', payload);
    return data;
  });
}

export function useCloseTicket() {
  return useTicketMutation(
    async (params: { id: number; id_facture?: number | null; annule?: boolean }) => {
      const { id, ...body } = params;
      const { data } = await api.post<JustificatifTicket>(`/tickets/${id}/close`, body);
      return data;
    },
  );
}

export function useRemindTicket() {
  return useTicketMutation(async (id: number) => {
    const { data } = await api.post<{ message: string }>(`/tickets/${id}/remind`);
    return data;
  });
}
