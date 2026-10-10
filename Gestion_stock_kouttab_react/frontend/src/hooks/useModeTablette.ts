import { useAuthStore } from '@/stores/auth';
import { USERNAME_TABLETTE, operateurDuJeton, operateurMemorise } from '@/lib/tablette';

/**
 * Le mode tablette est actif pour une session du compte système de la
 * tablette, et pour elle seule : une connexion ordinaire sur le même
 * navigateur ne l'hérite jamais.
 *
 * Le nom affiché vient de `sessionStorage` (posé par `/tablette`), à défaut du
 * profil (`operateur` de `/auth/me`) ou de la revendication `op` du jeton.
 */
export function useModeTablette(): { actif: boolean; operateur: string | null } {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const actif = Boolean(user && accessToken && user.username === USERNAME_TABLETTE);
  if (!actif) return { actif: false, operateur: null };
  return {
    actif,
    operateur: operateurMemorise() ?? user?.operateur ?? operateurDuJeton(accessToken),
  };
}
