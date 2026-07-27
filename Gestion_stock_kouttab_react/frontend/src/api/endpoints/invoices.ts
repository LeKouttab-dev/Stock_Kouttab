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

export interface CreateInvoicePayload {
  comment?: string;
  files: File[];
  poleId: number;
  /** Événement du référentiel, ou `null` si saisi à la main. */
  eventId?: number | null;
  eventLibre?: string;
  dateEvenement: string;
  fournisseur?: string;
  montant?: string;
}

async function createInvoice(payload: CreateInvoicePayload): Promise<Invoice> {
  const formData = new FormData();
  if (payload.comment) formData.append('commentaire', payload.comment);
  formData.append('id_pole', String(payload.poleId));
  formData.append('date_evenement', payload.dateEvenement);
  // Exclusifs : le backend refuse les deux à la fois.
  if (payload.eventId != null) formData.append('id_event', String(payload.eventId));
  else if (payload.eventLibre?.trim())
    formData.append('evenement_libre', payload.eventLibre.trim());
  if (payload.fournisseur?.trim()) formData.append('fournisseur', payload.fournisseur.trim());
  if (payload.montant?.trim()) formData.append('montant', payload.montant.trim());
  payload.files.forEach((file) => formData.append('files', file));
  const { data } = await api.post<Invoice>('/invoices', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

async function resendComptaEmail(invoiceId: number): Promise<{ message: string }> {
  const { data } = await api.post(`/invoices/${invoiceId}/resend-compta-email`);
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

/** Relance l'envoi de la facture au service comptable (Compta / Super Admin). */
export function useResendComptaEmail() {
  return useApiMutation({ mutationFn: resendComptaEmail });
}
