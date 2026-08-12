/**
 * Remboursements groupés : un versement solde plusieurs notes d'un bénévole.
 *
 * Les listes de moyens et d'établissements viennent du serveur plutôt que
 * d'être recopiées ici : l'API les valide, et deux copies finiraient par
 * diverger au premier ajout.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import { expenseQueryKeys } from './expenses';
import { notificationQueryKeys } from './notifications';
import type { Reimbursement, ReimbursementOptions, VolunteerExpenses } from '@/types/api';

export const reimbursementQueryKeys = {
  all: ['reimbursements'] as const,
  list: () => [...reimbursementQueryKeys.all, 'list'] as const,
  byVolunteer: () => [...reimbursementQueryKeys.all, 'by-volunteer'] as const,
  options: () => [...reimbursementQueryKeys.all, 'options'] as const,
};

export interface CreateReimbursementPayload {
  expense_ids: number[];
  date_remboursement?: string;
  moyen?: string;
  etablissement?: string;
  approuve_par?: string;
  commentaire?: string;
}

export function useVolunteerExpenses() {
  return useQuery({
    queryKey: reimbursementQueryKeys.byVolunteer(),
    queryFn: async () => {
      const { data } = await api.get<VolunteerExpenses[]>('/reimbursements/by-volunteer');
      return data;
    },
  });
}

export function useReimbursements() {
  return useQuery({
    queryKey: reimbursementQueryKeys.list(),
    queryFn: async () => {
      const { data } = await api.get<Reimbursement[]>('/reimbursements');
      return data;
    },
  });
}

export function useReimbursementOptions() {
  return useQuery({
    queryKey: reimbursementQueryKeys.options(),
    queryFn: async () => {
      const { data } = await api.get<ReimbursementOptions>('/reimbursements/options');
      return data;
    },
    // Listes figées côté serveur : inutile de les redemander à chaque ouverture
    // de la fenêtre de remboursement.
    staleTime: 60 * 60 * 1000,
  });
}

export function useCreateReimbursement() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (payload: CreateReimbursementPayload) => {
      const { data } = await api.post<Reimbursement>('/reimbursements', payload);
      return data;
    },
    // Un remboursement change l'état des notes, les totaux par bénévole et le
    // nombre de dossiers à traiter : les trois vues doivent suivre.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reimbursementQueryKeys.all });
      qc.invalidateQueries({ queryKey: expenseQueryKeys.all });
      qc.invalidateQueries({ queryKey: notificationQueryKeys.all });
    },
  });
}

/** Chemin de téléchargement d'un justificatif, à passer à `useDownloadAttachment`. */
export function reimbursementDocumentPath(id: number, format: 'pdf' | 'xlsx'): string {
  return `/reimbursements/${id}/document?format=${format}`;
}
