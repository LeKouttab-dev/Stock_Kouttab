import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { DatabaseStatus, OutboundEmail } from '@/types/api';

export const adminQueryKeys = {
  databaseStatus: ['admin', 'database', 'status'] as const,
  outboundEmails: ['admin', 'outbound-emails'] as const,
};

/** Les envois anciens n'apprennent plus rien : seule la file récente compte. */
const OUTBOUND_EMAILS_LIMIT = 50;

async function fetchDatabaseStatus(): Promise<DatabaseStatus> {
  const { data } = await api.get<DatabaseStatus>('/admin/database/status');
  return data;
}

async function exportDatabase(): Promise<Blob> {
  const response = await api.post('/admin/database/export', null, { responseType: 'blob' });
  return response.data as Blob;
}

async function importDatabase(
  files: File[],
): Promise<{ tables: Array<{ name: string; rows: number }> }> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  const { data } = await api.post<{ tables: Array<{ name: string; rows: number }> }>(
    '/admin/database/import',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Le backend exige confirm=true pour éviter une perte de données accidentelle.
      // La confirmation utilisateur est déjà gérée par la checkbox côté UI.
      params: { confirm: true },
    },
  );
  return data;
}

export function useDatabaseStatus() {
  return useQuery({ queryKey: adminQueryKeys.databaseStatus, queryFn: fetchDatabaseStatus });
}

export function useExportDatabase() {
  return useApiMutation({
    mutationFn: exportDatabase,
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      a.href = url;
      a.download = `kouttab-export-${ts}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    },
  });
}

export function useImportDatabase() {
  return useApiMutation({ mutationFn: importDatabase });
}

async function fetchOutboundEmails(): Promise<OutboundEmail[]> {
  const { data } = await api.get<OutboundEmail[]>('/admin/outbound-emails', {
    params: { limit: OUTBOUND_EMAILS_LIMIT },
  });
  return data;
}

async function retryOutboundEmail(id: number): Promise<void> {
  await api.post(`/admin/outbound-emails/${id}/retry`);
}

export function useOutboundEmails() {
  return useQuery({ queryKey: adminQueryKeys.outboundEmails, queryFn: fetchOutboundEmails });
}

export function useRetryOutboundEmail() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: retryOutboundEmail,
    onSuccess: () => qc.invalidateQueries({ queryKey: adminQueryKeys.outboundEmails }),
  });
}
