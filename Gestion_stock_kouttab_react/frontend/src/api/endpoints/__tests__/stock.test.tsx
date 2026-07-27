import { describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { server } from '@/test/mocks/server';
import { createTestQueryClient } from '@/test/test-utils';
import { useStockItems, useCreateStockItem, stockQueryKeys } from '../stock';
import { useToastList } from '@/hooks/useToast';
import { mockStockItems } from '@/test/mocks/handlers';

const BASE_URL = 'http://localhost:8000/api/v1';

function withClient() {
  const qc = createTestQueryClient();
  return {
    qc,
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
}

describe('api/endpoints/stock', () => {
  it('useStockItems returns the mocked items', async () => {
    const { wrapper } = withClient();
    const { result } = renderHook(() => useStockItems(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(mockStockItems.length);
    expect(result.current.data?.[0].nom).toBe(mockStockItems[0].nom);
  });

  it('useCreateStockItem invalidates stock queries on success', async () => {
    const { qc, wrapper } = withClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useCreateStockItem(), { wrapper });

    result.current.mutate({
      nom: 'Thé',
      categorie: 'Nourriture',
      sous_categorie: 'Boissons',
      quantite: 5,
      seuil_alerte: 2,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: stockQueryKeys.all });
  });

  it('useCreateStockItem shows an error toast on 409 (CONF_4002)', async () => {
    server.use(
      http.post(`${BASE_URL}/stock/items`, () =>
        HttpResponse.json(
          { code: 'CONF_4002', message: 'Existe déjà' },
          { status: 409 },
        ),
      ),
    );

    const { wrapper } = withClient();
    const { result } = renderHook(() => useCreateStockItem(), { wrapper });

    result.current.mutate({
      nom: 'Café',
      categorie: 'Nourriture',
      sous_categorie: 'Boissons',
      quantite: 1,
      seuil_alerte: 1,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const { result: toasts } = renderHook(() => useToastList());
    const errorToasts = toasts.current.filter((t) => t.variant === 'error');
    expect(errorToasts.length).toBeGreaterThan(0);
    expect(errorToasts[0].description).toMatch(/CONF_4002/);
  });
});
