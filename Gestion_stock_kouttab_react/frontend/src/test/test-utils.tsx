import { type ReactElement, type ReactNode } from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth';

interface ProvidersOptions {
  /** Si fourni, on utilise un MemoryRouter avec ces entries au lieu du BrowserRouter. */
  routerEntries?: string[];
  /** Permet d'injecter un QueryClient externe (pratique pour tester invalidation). */
  queryClient?: QueryClient;
}

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
    // Pas de logger d'erreur bruyant pendant les tests
  });
}

interface AllProvidersProps {
  children: ReactNode;
  options: ProvidersOptions;
}

function AllProviders({ children, options }: AllProvidersProps) {
  const qc = options.queryClient ?? createTestQueryClient();
  const Router = options.routerEntries ? MemoryRouter : BrowserRouter;
  const routerProps = options.routerEntries
    ? { initialEntries: options.routerEntries }
    : {};
  return (
    <QueryClientProvider client={qc}>
      <Router {...(routerProps as Record<string, unknown>)}>{children}</Router>
    </QueryClientProvider>
  );
}

export interface RenderWithProvidersOptions
  extends Omit<RenderOptions, 'wrapper'>,
    ProvidersOptions {}

/**
 * Render un composant React enveloppé dans QueryClientProvider + Router,
 * et nettoie le store d'auth avant le rendu.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult & { queryClient: QueryClient } {
  // Toujours partir d'un store auth propre.
  useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });

  const queryClient = options.queryClient ?? createTestQueryClient();
  const { routerEntries, queryClient: _qc, ...rtlOptions } = options;
  const result = render(ui, {
    wrapper: ({ children }) => (
      <AllProviders options={{ queryClient, routerEntries }}>{children}</AllProviders>
    ),
    ...rtlOptions,
  });

  return { ...result, queryClient };
}

// Réexports RTL pour tout avoir dans un seul import.
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
