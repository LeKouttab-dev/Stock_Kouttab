import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AxiosError, AxiosHeaders } from 'axios';
import { useApiMutation } from './useApiMutation';
import { useToastList } from './useToast';

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function makeAxiosError(code = 'AUTH_1001'): AxiosError {
  const err = new AxiosError('Failed');
  err.response = {
    status: 401,
    statusText: 'Unauthorized',
    data: { code, message: 'Invalid' },
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe('hooks/useApiMutation', () => {
  it('runs onSuccess and does NOT push an error toast on success', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    let onSuccessCalled = false;

    const { result } = renderHook(
      () =>
        useApiMutation<string, Error, void>({
          mutationFn: async () => 'ok',
          onSuccess: () => {
            onSuccessCalled = true;
          },
        }),
      { wrapper: wrapper(qc) },
    );

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(onSuccessCalled).toBe(true);
    // No error toast should have been pushed
    const { result: toastList } = renderHook(() => useToastList());
    expect(toastList.current.filter((t) => t.variant === 'error')).toHaveLength(0);
  });

  it('shows an error toast on failure (default behavior)', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const err = makeAxiosError();

    const { result } = renderHook(
      () =>
        useApiMutation<unknown, AxiosError, void>({
          mutationFn: async () => {
            throw err;
          },
        }),
      { wrapper: wrapper(qc) },
    );

    result.current.mutate();
    await waitFor(() => expect(result.current.isError).toBe(true));

    const { result: toastList } = renderHook(() => useToastList());
    const errorToasts = toastList.current.filter((t) => t.variant === 'error');
    expect(errorToasts.length).toBeGreaterThan(0);
    expect(errorToasts[0].title).toBe('Erreur');
  });

  it('does NOT show a toast when silentToast=true', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const err = makeAxiosError();
    let onErrorCalled = false;

    const { result } = renderHook(
      () =>
        useApiMutation<unknown, AxiosError, void>({
          mutationFn: async () => {
            throw err;
          },
          silentToast: true,
          onError: () => {
            onErrorCalled = true;
          },
        }),
      { wrapper: wrapper(qc) },
    );

    result.current.mutate();
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(onErrorCalled).toBe(true);
    const { result: toastList } = renderHook(() => useToastList());
    expect(toastList.current.filter((t) => t.variant === 'error')).toHaveLength(0);
  });
});
