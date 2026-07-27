import {
  useMutation,
  type DefaultError,
  type UseMutationOptions,
  type UseMutationResult,
} from '@tanstack/react-query';
import { useApiErrorToast } from './useApiErrorToast';

/**
 * Variante de `useMutation` qui affiche automatiquement un toast d'erreur en
 * cas d'échec, tout en respectant un éventuel `onError` fourni par l'appelant.
 *
 * Le toast est branché AVANT le `onError` du caller : si tu veux empêcher le
 * toast (par ex. pour le login où on affiche une `<ErrorAlert>` à la place),
 * passe `silentToast: true`.
 *
 * Usage :
 * ```ts
 * useApiMutation({
 *   mutationFn: createItem,
 *   onSuccess: () => toast.success('Article créé'),
 *   // toast d'erreur automatique + invalidation
 *   onError: () => qc.invalidateQueries({ queryKey: ['stock'] }),
 * });
 * ```
 */
export function useApiMutation<
  TData = unknown,
  TError = DefaultError,
  TVariables = void,
  TContext = unknown,
>(
  options: UseMutationOptions<TData, TError, TVariables, TContext> & {
    silentToast?: boolean;
  },
): UseMutationResult<TData, TError, TVariables, TContext> {
  const showError = useApiErrorToast();
  const { silentToast, onError, ...rest } = options;
  return useMutation<TData, TError, TVariables, TContext>({
    ...rest,
    onError: (err, variables, context) => {
      if (!silentToast) showError(err);
      onError?.(err, variables, context);
    },
  });
}
