import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { Role, User, ValidationStatus } from '@/types/api';

export const userQueryKeys = {
  all: ['users'] as const,
  list: () => [...userQueryKeys.all, 'list'] as const,
  pending: () => [...userQueryKeys.all, 'pending'] as const,
};

async function fetchUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>('/users');
  return data;
}

async function fetchPendingUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>('/users/pending');
  return data;
}

async function validateUser(params: {
  id: number;
  status: Extract<ValidationStatus, 'active' | 'rejected'>;
}): Promise<User> {
  // Le corps attendu est `validation_status` (cf. UserValidate, schemas/user.py).
  // Envoyer `status` faisait echouer toute validation de compte en 422.
  const { data } = await api.patch<User>(`/users/${params.id}/validate`, {
    validation_status: params.status,
  });
  return data;
}

async function updateUserRole(params: { id: number; role: Role }): Promise<User> {
  const { data } = await api.patch<User>(`/users/${params.id}/role`, { role: params.role });
  return data;
}

async function deleteUser(id: number): Promise<void> {
  await api.delete(`/users/${id}`);
}

export function useUsers() {
  return useQuery({ queryKey: userQueryKeys.list(), queryFn: fetchUsers });
}

export function usePendingUsers() {
  return useQuery({ queryKey: userQueryKeys.pending(), queryFn: fetchPendingUsers });
}

export function useValidateUser() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: validateUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: userQueryKeys.all });
    },
  });
}

export function useUpdateUserRole() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateUserRole,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: userQueryKeys.all });
    },
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: userQueryKeys.all });
    },
  });
}
