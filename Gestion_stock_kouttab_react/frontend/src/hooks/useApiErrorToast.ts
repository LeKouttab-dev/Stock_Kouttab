import { useCallback } from 'react';
import { useToast } from './useToast';
import { getErrorCode, getErrorMessage } from '@/lib/errors';

/**
 * Hook utilitaire pour afficher proprement une erreur API dans un toast.
 *
 * Usage typique dans un `useMutation` :
 * ```ts
 * const showError = useApiErrorToast();
 * useMutation({
 *   mutationFn: ...,
 *   onError: (err) => showError(err),
 * });
 * ```
 *
 * Le toast affiche le message catalogué côté frontend (cf.
 * `lib/errors.ts`). Le code d'erreur (ex. `AUTH_1001`) est ajouté en
 * petit dans la description pour faciliter le support.
 */
export function useApiErrorToast() {
  const { error: errorToast } = useToast();
  return useCallback(
    (err: unknown, fallback?: string) => {
      const message = getErrorMessage(err, fallback ?? 'Une erreur est survenue.');
      const code = getErrorCode(err);
      errorToast('Erreur', code ? `${message} (${code})` : message);
    },
    [errorToast],
  );
}
