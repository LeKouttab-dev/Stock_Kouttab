import { useQuery } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { DatabaseStatus } from '@/types/api';

export const adminQueryKeys = {
  databaseStatus: ['admin', 'database', 'status'] as const,
};

async function fetchDatabaseStatus(): Promise<DatabaseStatus> {
  const { data } = await api.get<DatabaseStatus>('/admin/database/status');
  return data;
}

async function exportDatabase(): Promise<Blob> {
  const response = await api.post('/admin/database/export', null, { responseType: 'blob' });
  return response.data as Blob;
}

async function importDatabase(files: File[]): Promise<{ tables: Array<{ name: string; rows: number }> }> {
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
