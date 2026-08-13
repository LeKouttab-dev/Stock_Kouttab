import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type {
  Expense,
  ExpenseCreateRequest,
  ExpenseUpdateRequest,
  ExpenseValidateRequest,
} from '@/types/api';

export const expenseQueryKeys = {
  all: ['expenses'] as const,
  mine: () => [...expenseQueryKeys.all, 'mine'] as const,
  list: () => [...expenseQueryKeys.all, 'list'] as const,
  files: (id: number) => [...expenseQueryKeys.all, 'files', id] as const,
};

async function fetchMyExpenses(): Promise<Expense[]> {
  const { data } = await api.get<Expense[]>('/expenses/me');
  return data;
}

/**
 * Toutes les notes, **archives comprises**.
 *
 * Un seul appel plutôt qu'un par filtre : l'écran groupe et compte déjà les
 * notes localement, et la base est distante — un aller-retour par changement de
 * filtre coûterait plus cher que les quelques lignes archivées rapatriées.
 */
async function fetchAllExpenses(): Promise<Expense[]> {
  const { data } = await api.get<Expense[]>('/expenses', {
    params: { include_archived: true },
  });
  return data;
}

/**
 * Champs qui n'existent que dans le formulaire.
 *
 * `requiert_evenement` recopie le réglage du pôle pour que Zod puisse valider
 * conditionnellement ; l'API le déduit elle-même du pôle et n'en veut pas.
 */
const CHAMPS_INTERNES = new Set(['requiert_evenement']);

async function createExpense(payload: ExpenseCreateRequest, files: File[]): Promise<Expense> {
  const formData = new FormData();
  Object.entries(payload).forEach(([k, v]) => {
    if (CHAMPS_INTERNES.has(k)) return;
    if (v !== undefined && v !== null && v !== '') formData.append(k, String(v));
  });
  files.forEach((file) => formData.append('files', file));
  const { data } = await api.post<Expense>('/expenses', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

async function updateExpense(params: { id: number; data: ExpenseUpdateRequest }): Promise<Expense> {
  const { data } = await api.patch<Expense>(`/expenses/${params.id}`, params.data);
  return data;
}

/** Archive la note : elle sort des listes courantes sans quitter la base. */
async function archiveExpense(id: number): Promise<void> {
  await api.delete(`/expenses/${id}`);
}

async function restoreExpense(id: number): Promise<void> {
  await api.post(`/expenses/${id}/restore`);
}

async function validateExpense(params: {
  id: number;
  payload: ExpenseValidateRequest;
}): Promise<Expense> {
  const { data } = await api.patch<Expense>(`/expenses/${params.id}/validate`, params.payload);
  return data;
}

// `getExpenseFileUrl` a été retiré : il construisait une URL destinée à un
// `<a href>`, or une navigation ne porte pas l'en-tête `Authorization` et le
// téléchargement revenait toujours en `AUTH_1011`. Passer par
// `useDownloadAttachment`, qui télécharge via axios.

export function useMyExpenses() {
  return useQuery({ queryKey: expenseQueryKeys.mine(), queryFn: fetchMyExpenses });
}

export function useAllExpenses() {
  return useQuery({ queryKey: expenseQueryKeys.list(), queryFn: fetchAllExpenses });
}

export function useCreateExpense() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: ({ payload, files }: { payload: ExpenseCreateRequest; files: File[] }) =>
      createExpense(payload, files),
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseQueryKeys.all }),
  });
}

export function useUpdateExpense() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateExpense,
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseQueryKeys.all }),
  });
}

export function useArchiveExpense() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: archiveExpense,
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseQueryKeys.all }),
  });
}

export function useRestoreExpense() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: restoreExpense,
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseQueryKeys.all }),
  });
}

export function useValidateExpense() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: validateExpense,
    onSuccess: () => qc.invalidateQueries({ queryKey: expenseQueryKeys.all }),
  });
}
