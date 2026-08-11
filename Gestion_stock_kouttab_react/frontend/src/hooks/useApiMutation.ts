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

  // Les arguments sont relayés tels quels plutôt que déstructurés : l'arité de
  // `onError` a changé entre versions de TanStack Query, et une signature figée
  // casse la compilation à la mise à jour.
  type OnErrorArgs = Parameters<
    NonNullable<UseMutationOptions<TData, TError, TVariables, TContext>['onError']>
  >;

  return useMutation<TData, TError, TVariables, TContext>({
    ...rest,
    onError: (...args: OnErrorArgs) => {
      if (!silentToast) showError(args[0]);
      return onError?.(...args);
    },
  });
}
