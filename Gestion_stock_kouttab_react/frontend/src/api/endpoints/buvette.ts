import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type {
  BuvetteProduct,
  CaisseAppVersion,
  BuvetteProductCreate,
  BuvetteProductUpdate,
  BuvetteSale,
  SyncResult,
  WebhookConfigureRequest,
  WebhookStatus,
} from '@/types/api';

export const buvetteQueryKeys = {
  all: ['buvette'] as const,
  products: () => [...buvetteQueryKeys.all, 'products'] as const,
  sales: (filters?: Record<string, unknown>) =>
    [...buvetteQueryKeys.all, 'sales', filters ?? {}] as const,
  webhook: () => [...buvetteQueryKeys.all, 'webhook'] as const,
};

/* ---------- Products ---------- */
async function fetchProducts(): Promise<BuvetteProduct[]> {
  const { data } = await api.get<BuvetteProduct[]>('/buvette/products');
  return data;
}

async function createProduct(payload: BuvetteProductCreate): Promise<BuvetteProduct> {
  const { data } = await api.post<BuvetteProduct>('/buvette/products', payload);
  return data;
}

async function updateProduct(params: {
  id: number;
  data: BuvetteProductUpdate;
}): Promise<BuvetteProduct> {
  const { data } = await api.patch<BuvetteProduct>(`/buvette/products/${params.id}`, params.data);
  return data;
}

async function deleteProduct(id: number): Promise<void> {
  await api.delete(`/buvette/products/${id}`);
}

/* ---------- Sales ---------- */
async function fetchSales(limit = 50, offset = 0): Promise<BuvetteSale[]> {
  const { data } = await api.get<BuvetteSale[]>('/buvette/sales', {
    params: { limit, offset },
  });
  return data;
}

/* ---------- Sync ---------- */
async function syncBuvette(): Promise<SyncResult> {
  const { data } = await api.post<SyncResult>('/buvette/sync');
  return data;
}

/* ---------- Webhook ---------- */
async function fetchWebhookStatus(): Promise<WebhookStatus> {
  const { data } = await api.get<WebhookStatus>('/buvette/webhook/status');
  return data;
}

async function configureWebhook(payload?: WebhookConfigureRequest): Promise<WebhookStatus> {
  const { data } = await api.post<WebhookStatus>('/buvette/webhook/configure', payload ?? {});
  return data;
}

async function deleteWebhook(): Promise<void> {
  await api.delete('/buvette/webhook');
}

/* ---------- Hooks ---------- */
export function useBuvetteProducts() {
  return useQuery({
    queryKey: buvetteQueryKeys.products(),
    queryFn: fetchProducts,
  });
}

export function useBuvetteSales(limit = 50, offset = 0) {
  return useQuery({
    queryKey: buvetteQueryKeys.sales({ limit, offset }),
    queryFn: () => fetchSales(limit, offset),
  });
}

export function useCreateBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useUpdateBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

/**
 * Dépose la photo d'un produit : prise au téléphone, ou choisie sur l'ordinateur.
 *
 * Le serveur la réduit à 600 px et lui donne une adresse NEUVE à chaque dépôt —
 * la tablette met les photos en cache par URL en ignorant les en-têtes, une
 * même adresse y garderait l'ancienne image.
 */
export function useUploadBuvettePhoto() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => {
      const corps = new FormData();
      corps.append('file', file);
      const { data } = await api.post<BuvetteProduct>(`/buvette/products/${id}/photo`, corps);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

/** Retire la photo : la tablette reprend l'emoji, jamais une case vide. */
export function useDeleteBuvettePhoto() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete<BuvetteProduct>(`/buvette/products/${id}/photo`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useDeleteBuvetteProduct() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteProduct,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useSyncBuvette() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: syncBuvette,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.products() }),
  });
}

export function useWebhookStatus() {
  return useQuery({
    queryKey: buvetteQueryKeys.webhook(),
    queryFn: fetchWebhookStatus,
  });
}

export function useConfigureWebhook() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: (payload?: WebhookConfigureRequest) => configureWebhook(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.webhook() }),
  });
}

export function useDeleteWebhook() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => qc.invalidateQueries({ queryKey: buvetteQueryKeys.webhook() }),
  });
}

/* ---- Application de la tablette de caisse ------------------------------- */

export const caisseAppQueryKey = ['buvette', 'app-caisse'] as const;

/** La version servie aux tablettes, ou `null` si rien n'a été publié. */
export function useCaisseAppVersion(actif = true) {
  return useQuery({
    queryKey: caisseAppQueryKey,
    enabled: actif,
    queryFn: async () => {
      const { data } = await api.get<CaisseAppVersion | null>('/buvette/app');
      return data;
    },
  });
}

/**
 * Publie l'APK que les tablettes installeront à leur prochain réveil.
 *
 * Délai généreux : le fichier pèse des dizaines de mégaoctets, là où les
 * autres appels de l'application se comptent en kilo-octets.
 */
export function usePublierCaisseApp() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async ({
      file,
      version_code,
      version_name,
    }: {
      file: File;
      version_code: number;
      version_name: string;
    }) => {
      const corps = new FormData();
      corps.append('file', file);
      corps.append('version_code', String(version_code));
      corps.append('version_name', version_name);
      const { data } = await api.post<CaisseAppVersion>('/buvette/app', corps, {
        timeout: 300_000,
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: caisseAppQueryKey }),
  });
}

/** Retire la version publiée. Les tablettes gardent celle qu'elles exécutent. */
export function useRetirerCaisseApp() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: async () => {
      const { data } = await api.delete('/buvette/app');
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: caisseAppQueryKey }),
  });
}
