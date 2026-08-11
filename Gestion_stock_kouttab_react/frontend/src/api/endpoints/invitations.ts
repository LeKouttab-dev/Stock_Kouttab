import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { AdminInvitation, CreateInvitationRequest } from '@/types/api';

export const invitationQueryKeys = {
  all: ['invitations'] as const,
  list: () => [...invitationQueryKeys.all, 'list'] as const,
};

async function fetchInvitations(): Promise<AdminInvitation[]> {
  const { data } = await api.get<AdminInvitation[]>('/invitations');
  return data;
}

async function createInvitation(payload: CreateInvitationRequest): Promise<AdminInvitation> {
  const { data } = await api.post<AdminInvitation>('/invitations', payload);
  return data;
}

async function deleteInvitation(id: number): Promise<void> {
  await api.delete(`/invitations/${id}`);
}

export function useInvitations() {
  return useQuery({ queryKey: invitationQueryKeys.list(), queryFn: fetchInvitations });
}

export function useCreateInvitation() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createInvitation,
    onSuccess: () => qc.invalidateQueries({ queryKey: invitationQueryKeys.all }),
  });
}

export function useDeleteInvitation() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteInvitation,
    onSuccess: () => qc.invalidateQueries({ queryKey: invitationQueryKeys.all }),
  });
}
