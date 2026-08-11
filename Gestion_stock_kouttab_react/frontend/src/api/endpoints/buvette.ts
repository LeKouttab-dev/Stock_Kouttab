import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type {
  BuvetteProduct,
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
