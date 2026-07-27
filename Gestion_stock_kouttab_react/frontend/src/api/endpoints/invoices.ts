import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { Invoice, InvoiceStatus } from '@/types/api';

export const invoiceQueryKeys = {
  all: ['invoices'] as const,
  mine: () => [...invoiceQueryKeys.all, 'mine'] as const,
  list: (filters?: Record<string, unknown>) => [...invoiceQueryKeys.all, 'list', filters ?? {}] as const,
};

async function fetchMyInvoices(): Promise<Invoice[]> {
  const { data } = await api.get<Invoice[]>('/invoices/me');
  return data;
}

async function fetchAllInvoices(filters?: { status?: string; date?: string; search?: string }): Promise<Invoice[]> {
  const { data } = await api.get<Invoice[]>('/invoices', { params: filters });
  return data;
}

async function createInvoice(payload: { comment?: string; files: File[] }): Promise<Invoice> {
  const formData = new FormData();
  if (payload.comment) formData.append('commentaire', payload.comment);
  payload.files.forEach((file) => formData.append('files', file));
  const { data } = await api.post<Invoice>('/invoices', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

async function updateInvoiceStatus(params: { id: number; status: InvoiceStatus }): Promise<Invoice> {
  const { data } = await api.patch<Invoice>(`/invoices/${params.id}/status`, { status: params.status });
  return data;
}

export function getInvoiceFileUrl(invoiceId: number, fileId: number): string {
  const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';
  return `${baseUrl}/invoices/${invoiceId}/files/${fileId}`;
}

export function useMyInvoices() {
  return useQuery({ queryKey: invoiceQueryKeys.mine(), queryFn: fetchMyInvoices });
}

export function useInvoices(filters?: { status?: string; date?: string; search?: string }) {
  return useQuery({
    queryKey: invoiceQueryKeys.list(filters),
    queryFn: () => fetchAllInvoices(filters),
  });
}

export function useCreateInvoice() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createInvoice,
    onSuccess: () => qc.invalidateQueries({ queryKey: invoiceQueryKeys.all }),
  });
}

export function useUpdateInvoiceStatus() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateInvoiceStatus,
    onSuccess: () => qc.invalidateQueries({ queryKey: invoiceQueryKeys.all }),
  });
}
