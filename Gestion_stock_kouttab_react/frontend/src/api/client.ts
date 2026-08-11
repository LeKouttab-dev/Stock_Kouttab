import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/auth';
import { getErrorCode, getErrorMessage } from '@/lib/errors';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

/* ---------- Request: attach JWT ---------- */
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

/* ---------- Response: refresh on 401 / TOKEN_EXPIRED ---------- */
type FailedQueueItem = {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
};
let isRefreshing = false;
let queue: FailedQueueItem[] = [];

function flushQueue(error: unknown, token: string | null = null) {
  queue.forEach((p) => (error || !token ? p.reject(error) : p.resolve(token)));
  queue = [];
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (!error.response || !original) return Promise.reject(error);

    const code = getErrorCode(error);
    const status = error.response.status;

    if (import.meta.env.DEV) {
      // Helpful for debugging — never logged in prod (stripped by Vite).
      console.warn(
        `[api] ${original.method?.toUpperCase()} ${original.url} -> ${status} ${code ?? ''}`,
      );
    }

    const isAuthEndpoint =
      original.url?.includes('/auth/login') || original.url?.includes('/auth/refresh');

    // Refresh on a 401 (or explicit TOKEN_EXPIRED), unless it's an auth endpoint.
    const shouldTryRefresh =
      !original._retry && !isAuthEndpoint && (status === 401 || code === 'AUTH_1010');

    if (shouldTryRefresh) {
      const refreshToken = useAuthStore.getState().refreshToken;
      if (!refreshToken) {
        useAuthStore.getState().logout();
        return Promise.reject(error);
      }
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push({
            resolve: (token: string) => {
              original.headers = original.headers ?? {};
              (original.headers as Record<string, string>).Authorization = `Bearer ${token}`;
              resolve(api(original));
            },
            reject,
          });
        });
      }

      original._retry = true;
      isRefreshing = true;
      try {
        const { data } = await axios.post<{ access_token: string; refresh_token?: string }>(
          `${BASE_URL}/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { 'Content-Type': 'application/json' } },
        );
        useAuthStore.getState().setTokens({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
        });
        flushQueue(null, data.access_token);
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (refreshErr) {
        flushQueue(refreshErr, null);
        useAuthStore.getState().logout();
        if (typeof window !== 'undefined') {
          window.location.assign('/login');
        }
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

/**
 * Backwards-compatible message extractor.
 *
 * Prefer the typed helpers from `@/lib/errors` (`getErrorMessage`,
 * `getErrorCode`) in new code. This export is kept so existing imports
 * (LoginPage, SignupPage, …) keep working.
 */
export function extractErrorMessage(err: unknown, fallback?: string): string {
  return getErrorMessage(err, fallback);
}
