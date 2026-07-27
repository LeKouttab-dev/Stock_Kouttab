import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { useApiMutation } from '@/hooks/useApiMutation';
import type {
  BarcodeLookupResponse,
  Category,
  CsvImportResponse,
  StockItem,
  StockItemCreate,
  StockItemUpdate,
  StockModification,
  StockStatistics,
  SubCategory,
} from '@/types/api';

export const stockQueryKeys = {
  all: ['stock'] as const,
  items: (filters?: Record<string, unknown>) =>
    [...stockQueryKeys.all, 'items', filters ?? {}] as const,
  categories: () => [...stockQueryKeys.all, 'categories'] as const,
  subcategories: (category?: string) => [...stockQueryKeys.all, 'subcategories', category] as const,
  statistics: () => [...stockQueryKeys.all, 'statistics'] as const,
  lowStock: () => [...stockQueryKeys.all, 'low'] as const,
  modifications: (filters?: Record<string, unknown>) =>
    [...stockQueryKeys.all, 'modifications', filters ?? {}] as const,
};

/* ---------- Items ---------- */
async function fetchItems(filters?: { category?: string; subcategory?: string; alert?: boolean }): Promise<StockItem[]> {
  const { data } = await api.get<StockItem[]>('/stock/items', { params: filters });
  return data;
}

async function createItem(payload: StockItemCreate): Promise<StockItem> {
  const { data } = await api.post<StockItem>('/stock/items', payload);
  return data;
}

async function updateItem(params: { id: number; data: StockItemUpdate }): Promise<StockItem> {
  const { data } = await api.patch<StockItem>(`/stock/items/${params.id}`, params.data);
  return data;
}

async function deleteItem(id: number): Promise<void> {
  await api.delete(`/stock/items/${id}`);
}

async function importCsv(file: File, skiprows = 6): Promise<CsvImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('skiprows', String(skiprows));
  const { data } = await api.post<CsvImportResponse>('/stock/items/import-csv', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/* ---------- Categories ---------- */
async function fetchCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>('/stock/categories');
  return data;
}

async function createCategory(nom: string): Promise<Category> {
  const { data } = await api.post<Category>('/stock/categories', { nom });
  return data;
}

async function renameCategory(params: { oldName: string; newName: string }): Promise<Category> {
  const { data } = await api.patch<Category>(`/stock/categories/${encodeURIComponent(params.oldName)}`, {
    nom: params.newName,
  });
  return data;
}

async function deleteCategory(name: string): Promise<void> {
  await api.delete(`/stock/categories/${encodeURIComponent(name)}`);
}

/* ---------- Subcategories ---------- */
async function fetchSubcategories(category?: string): Promise<SubCategory[]> {
  const { data } = await api.get<SubCategory[]>('/stock/subcategories', {
    params: category ? { category } : undefined,
  });
  return data;
}

async function createSubcategory(payload: { nom_categorie: string; nom_sous_categorie: string }): Promise<SubCategory> {
  const { data } = await api.post<SubCategory>('/stock/subcategories', payload);
  return data;
}

async function updateSubcategory(params: { id: number; data: { nom_sous_categorie: string } }): Promise<SubCategory> {
  const { data } = await api.patch<SubCategory>(`/stock/subcategories/${params.id}`, params.data);
  return data;
}

async function deleteSubcategory(id: number): Promise<void> {
  await api.delete(`/stock/subcategories/${id}`);
}

/* ---------- Stats / alerts / modifications ---------- */
async function fetchStatistics(): Promise<StockStatistics> {
  const { data } = await api.get<StockStatistics>('/stock/statistics');
  return data;
}

async function fetchLowStock(): Promise<StockItem[]> {
  const { data } = await api.get<StockItem[]>('/stock/low-stock');
  return data;
}

async function fetchModifications(filters?: { status?: string; days?: number }): Promise<StockModification[]> {
  const { data } = await api.get<StockModification[]>('/stock/modifications', { params: filters });
  return data;
}

async function createModification(payload: { id_stock: number; quantite_demandee: number }): Promise<StockModification> {
  const { data } = await api.post<StockModification>('/stock/modifications', payload);
  return data;
}

async function approveModification(id: number): Promise<StockModification> {
  const { data } = await api.post<StockModification>(`/stock/modifications/${id}/approve`);
  return data;
}

async function refuseModification(id: number): Promise<StockModification> {
  const { data } = await api.post<StockModification>(`/stock/modifications/${id}/refuse`);
  return data;
}

async function sendStockAlert(): Promise<{ recipients: number; items: number }> {
  const { data } = await api.post<{ recipients: number; items: number }>('/stock/alert');
  return data;
}

/* ---------- Barcode lookup ---------- */
async function lookupBarcode(barcode: string): Promise<BarcodeLookupResponse> {
  const { data } = await api.get<BarcodeLookupResponse>(
    `/stock/lookup-barcode/${encodeURIComponent(barcode)}`,
  );
  return data;
}

/* ---------- Hooks ---------- */
export function useStockItems(filters?: { category?: string; subcategory?: string; alert?: boolean }) {
  return useQuery({
    queryKey: stockQueryKeys.items(filters),
    queryFn: () => fetchItems(filters),
  });
}

export function useCreateStockItem() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useUpdateStockItem() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useDeleteStockItem() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useImportCsv() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: ({ file, skiprows }: { file: File; skiprows?: number }) => importCsv(file, skiprows),
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: stockQueryKeys.categories(),
    queryFn: fetchCategories,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useRenameCategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: renameCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useSubcategories(category?: string) {
  return useQuery({
    queryKey: stockQueryKeys.subcategories(category),
    queryFn: () => fetchSubcategories(category),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateSubcategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createSubcategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useUpdateSubcategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: updateSubcategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useDeleteSubcategory() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: deleteSubcategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useStockStatistics() {
  return useQuery({
    queryKey: stockQueryKeys.statistics(),
    queryFn: fetchStatistics,
    staleTime: 60_000,
  });
}

export function useLowStock() {
  return useQuery({ queryKey: stockQueryKeys.lowStock(), queryFn: fetchLowStock });
}

export function useStockModifications(filters?: { status?: string; days?: number }) {
  return useQuery({
    queryKey: stockQueryKeys.modifications(filters),
    queryFn: () => fetchModifications(filters),
  });
}

export function useCreateStockModification() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: createModification,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useApproveModification() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: approveModification,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useRefuseModification() {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn: refuseModification,
    onSuccess: () => qc.invalidateQueries({ queryKey: stockQueryKeys.all }),
  });
}

export function useSendStockAlert() {
  return useApiMutation({ mutationFn: sendStockAlert });
}

export function useBarcodeLookup() {
  return useApiMutation({
    mutationFn: lookupBarcode,
    silentToast: true,
  });
}
