import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { Invoice, InvoiceStatus } from '@/types/api';

export const invoiceQueryKeys = {
  all: ['invoices'] as const,
  mine: () => [...invoiceQueryKeys.all, 'mine'] as const,
  list: (filters?: Record<string, unknown>) =>
    [...invoiceQueryKeys.all, 'list', filters ?? {}] as const,
};

async function fetchMyInvoices(): Promise<Invoice[]> {
  const { data } = await api.get<Invoice[]>('/invoices/me');
  return data;
}

/**
 * Toutes les factures, **archives comprises**.
 *
 * Un seul appel plutôt qu'un par filtre : l'écran compte et répartit déjà les
 * lignes localement, et la base est distante — un aller-retour à chaque
 * changement d'onglet coûterait plus que les quelques archives rapatriées.
 * Même parti que sur l'écran des notes de frais.
 */
async function fetchAllInvoices(filters?: {
  status?: string;
  date?: string;
  search?: string;
}): Promise<Invoice[]> {
  const { data } = await api.get<Invoice[]>('/invoices', {
    params: { ...filters, include_archived: true },
  });
  return data;
}

export interface CreateInvoicePayload {
  comment?: string;
  files: File[];
  poleId: number;
  /** Événement du référentiel, ou `null` si saisi à la main. */
  eventId?: number | null;
  eventLibre?: string;
  /** Vide sous un pôle sans événement : il n'y a alors rien à dater. */
  dateEvenement?: string;
  /** Rattachement des pôles sans événement (courses, goûter, matériel...). */
  categorieId?: number | null;
  fournisseur?: string;
  montant?: string;
}

async function createInvoice(payload: CreateInvoicePayload): Promise<Invoice> {
  const formData = new FormData();
  if (payload.comment) formData.append('commentaire', payload.comment);
  formData.append('id_pole', String(payload.poleId));
  // Événement et catégorie s'excluent, et le backend refuse le mélange : on
  // n'envoie que ce que le pôle attend, jamais un champ résiduel.
  if (payload.dateEvenement?.trim())
    formData.append('date_evenement', payload.dateEvenement.trim());
  if (payload.categorieId != null) formData.append('id_categorie', String(payload.categorieId));
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

/** Archive la facture : elle sort des listes sans quitter la base. */
async function archiverFacture(id: number): Promise<void> {
  await api.delete(`/invoices/${id}`);
}

async function restaurerFacture(id: number): Promise<void> {
  await api.post(`/invoices/${id}/restore`);
}

async function updateInvoiceStatus(params: {
  id: number;
  status: InvoiceStatus;
  /** Motif du comptable : un refus arrivait sans la moindre explication. */
  commentaires_compta?: string;
}): Promise<Invoice> {
  const { data } = await api.patch<Invoice>(`/invoices/${params.id}/status`, {
    status: params.status,
    commentaires_compta: params.commentaires_compta,
  });
  return data;
}

// Retiré pour la même raison que `getExpenseFileUrl` : une URL passée à un
// `<a href>` perd le jeton JWT. Cf. `useDownloadAttachment`.

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

export function useArchiverFacture() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: archiverFacture,
    onSuccess: () => qc.invalidateQueries({ queryKey: invoiceQueryKeys.all }),
  });
}

export function useRestaurerFacture() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: restaurerFacture,
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
