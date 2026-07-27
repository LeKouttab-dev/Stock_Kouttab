import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  getErrorCode,
  getErrorMessage,
  getErrorStatus,
} from '@/lib/errors';

interface ErrorAlertProps {
  /** Erreur brute (axios, Error, …) ou rien si on veut juste afficher un message custom. */
  error?: unknown;
  /** Message à afficher si l'erreur ne fournit rien d'exploitable. */
  fallback?: string;
  /** Titre de l'alerte. Défaut : "Erreur". */
  title?: string;
  /** Cache l'affichage du code d'erreur (utile pour les pages publiques). */
  hideCode?: boolean;
  className?: string;
}

/**
 * Alerte d'erreur réutilisable.
 *
 * Affiche le message lisible (`getErrorMessage`) et — par défaut — le code
 * d'erreur en petit pour faciliter le support utilisateur ("indiquez ce code
 * à l'administrateur").
 *
 * À utiliser dans les pages où un toast n'est pas adapté (ex. page entière en
 * erreur, formulaire de login, écran de validation d'invitation, etc.).
 */
export function ErrorAlert({
  error,
  fallback,
  title = 'Erreur',
  hideCode = false,
  className,
}: ErrorAlertProps) {
  const message = getErrorMessage(error, fallback);
  const code = getErrorCode(error);
  const status = getErrorStatus(error);

  return (
    <Alert variant="destructive" className={className}>
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {!hideCode && code && (
          <p className="mt-1 text-xs opacity-70">
            Code : <span className="font-mono">{code}</span>
            {status ? ` · HTTP ${status}` : ''}
          </p>
        )}
      </AlertDescription>
    </Alert>
  );
}
