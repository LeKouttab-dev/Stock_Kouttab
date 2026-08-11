import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { server } from '@/test/mocks/server';
import { createTestQueryClient } from '@/test/test-utils';
import { useValidateUser, useUpdateUserRole } from '../users';

const BASE_URL = 'http://localhost:8000/api/v1';

function withClient() {
  const qc = createTestQueryClient();
  return {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
}

/**
 * Ces tests figent le *nom des champs* envoyes a l'API, pas seulement le fait
 * qu'un appel parte. Le formulaire envoyait `status` la ou le backend attend
 * `validation_status` : la validation d'un compte echouait en 422, et aucun
 * test ne le voyait puisque le mock acceptait n'importe quel corps.
 */
describe('api/endpoints/users', () => {
  it('useValidateUser sends validation_status, as UserValidate expects', async () => {
    let body: unknown = null;
    server.use(
      http.patch(`${BASE_URL}/users/:id/validate`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          id: 2,
          username: 'omar',
          role: 'Benevole',
          validation_status: 'active',
        });
      }),
    );

    const { wrapper } = withClient();
    const { result } = renderHook(() => useValidateUser(), { wrapper });

    result.current.mutate({ id: 2, status: 'active' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(body).toEqual({ validation_status: 'active' });
  });

  it('useUpdateUserRole sends role', async () => {
    let body: unknown = null;
    server.use(
      http.patch(`${BASE_URL}/users/:id/role`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          id: 2,
          username: 'omar',
          role: 'Compta',
          validation_status: 'active',
        });
      }),
    );

    const { wrapper } = withClient();
    const { result } = renderHook(() => useUpdateUserRole(), { wrapper });

    result.current.mutate({ id: 2, role: 'Compta' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(body).toEqual({ role: 'Compta' });
  });
});
