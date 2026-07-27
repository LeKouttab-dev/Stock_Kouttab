/**
 * Catalogue centralisé des codes d'erreur de l'API et messages utilisateur
 * français associés.
 *
 * Tout nouveau code ajouté côté backend (`backend/app/core/errors.py`) doit être
 * répliqué ici, sinon le frontend retombera sur le message générique renvoyé
 * par l'API (qui reste lisible en français mais perd la possibilité d'avoir un
 * wording optimisé pour l'UI — par ex. avec des suggestions d'action).
 *
 * Pour ajouter un nouveau code :
 *   1. L'ajouter dans `ErrorCode` côté backend.
 *   2. Ajouter une entrée dans `ERROR_MESSAGES` côté backend.
 *   3. Ajouter la même clé ici avec un message adapté à l'UI.
 */

export const ERROR_MESSAGES: Record<string, string> = {
  // ---------------- Auth (1xxx) ----------------
  AUTH_1001:
    "Identifiants incorrects. Vérifiez votre nom d'utilisateur et votre mot de passe.",
  AUTH_1002: 'Votre compte est en attente de validation par un administrateur.',
  AUTH_1003: 'Votre compte a été refusé. Contactez un administrateur.',
  AUTH_1004:
    'Compte temporairement verrouillé. Réessayez dans 15 minutes.',
  AUTH_1010: 'Votre session a expiré. Reconnectez-vous.',
  AUTH_1011: 'Token invalide.',
  AUTH_1012: 'Vous devez être connecté pour effectuer cette action.',
  AUTH_1013: 'Le rafraîchissement a échoué. Reconnectez-vous.',
  AUTH_1020:
    'Mot de passe trop faible : 8 caractères min, une majuscule, une minuscule, un chiffre et un caractère spécial.',
  AUTH_1021: 'Vous devez changer votre mot de passe.',
  AUTH_1022: "Nom d'utilisateur invalide (3-20 caractères alphanumériques).",
  AUTH_1023: "Ce nom d'utilisateur est déjà pris.",
  AUTH_1024: 'Adresse email invalide.',
  AUTH_1025: 'Cette adresse email est déjà utilisée.',
  AUTH_1030: "Lien d'invitation invalide.",
  AUTH_1031: "Lien d'invitation expiré. Demandez-en un nouveau.",
  AUTH_1032: "Ce lien d'invitation a déjà été utilisé.",
  AUTH_1033: 'Trop de tentatives sur cette invitation.',

  // ---------------- Permissions (2xxx) ----------------
  PERM_2001: "Vous n'avez pas les droits nécessaires pour effectuer cette action.",
  PERM_2002: 'Cette action nécessite un rôle spécifique.',
  PERM_2003:
    'Vous ne pouvez pas effectuer cette action sur votre propre compte.',

  // ---------------- Resources (3xxx) ----------------
  RES_3001: 'Ressource introuvable.',
  RES_3002: 'Utilisateur introuvable.',
  RES_3003: 'Article introuvable.',
  RES_3004: 'Note de frais introuvable.',
  RES_3005: 'Facture introuvable.',
  RES_3006: 'Catégorie introuvable.',
  RES_3007: 'Sous-catégorie introuvable.',
  RES_3008: 'Produit de la buvette introuvable.',
  RES_3009: 'Invitation introuvable.',
  RES_3010: 'Fichier introuvable.',
  RES_3011: 'Demande de modification introuvable.',

  // ---------------- Conflicts (4xxx) ----------------
  CONF_4001: 'Conflit avec une ressource existante.',
  CONF_4002: 'Un article avec ce nom existe déjà.',
  CONF_4003:
    'Cette catégorie contient encore des articles. Déplacez-les avant de la supprimer.',
  CONF_4004: 'Cette sous-catégorie contient encore des articles.',
  CONF_4005:
    'Cette note de frais ne peut plus être modifiée (statut différent de « En attente »).',
  CONF_4006:
    'Seules les notes au statut « Remboursée » peuvent être supprimées.',
  CONF_4007: 'Cet utilisateur a des notes ou factures liées. Action impossible.',
  CONF_4008: 'Cette catégorie existe déjà.',
  CONF_4009: 'Cette sous-catégorie existe déjà.',
  CONF_4010: "Cette demande de modification n'est plus en attente.",

  // ---------------- Validation (5xxx) ----------------
  VAL_5001: 'Données invalides.',
  VAL_5002: 'Un ou plusieurs champs obligatoires sont manquants.',
  VAL_5003: 'Montant invalide (doit être positif).',
  VAL_5004: 'Quantité invalide (doit être un entier positif).',
  VAL_5005: 'Date invalide.',
  VAL_5006: 'Type de fichier non autorisé.',
  VAL_5007: 'Fichier trop volumineux (10 Mo maximum).',
  VAL_5008: "Trop de fichiers (5 maximum par envoi).",
  VAL_5009: 'Format CSV invalide. Vérifiez les colonnes attendues.',
  VAL_5010: "Le fichier n'est plus disponible sur le serveur.",

  // ---------------- External services (6xxx) ----------------
  EXT_6001:
    'Authentification HelloAsso échouée. Vérifiez les credentials dans les paramètres.',
  EXT_6002: "Erreur lors de l'appel à HelloAsso. Réessayez plus tard.",
  EXT_6003: 'Payload webhook ignoré (format inattendu).',
  EXT_6004: "L'intégration HelloAsso n'est pas configurée.",
  EXT_6010:
    "L'envoi de l'email a échoué. L'action a quand même été enregistrée.",
  EXT_6020: "Erreur base de données. Contactez l'administrateur.",

  // ---------------- Rate limit (7xxx) ----------------
  RATE_7001: 'Trop de requêtes. Patientez quelques instants.',
  RATE_7002:
    'Trop de tentatives de connexion. Réessayez dans 15 minutes.',

  // ---------------- Generic (9xxx) ----------------
  GEN_9001: "Erreur interne, contactez l'administrateur.",
  GEN_9002: 'Service temporairement indisponible.',
  GEN_9003: 'Requête invalide.',
};

/** Forme du payload d'erreur retourné par le backend. */
export interface ApiError {
  code: string;
  message: string;
  extras?: Record<string, unknown>;
}

interface AxiosLikeError {
  response?: {
    data?: Partial<ApiError> & { detail?: unknown };
    status?: number;
  };
  message?: string;
}

function asAxiosLike(error: unknown): AxiosLikeError | null {
  if (typeof error !== 'object' || error === null) return null;
  if (!('response' in error) && !('isAxiosError' in error)) return null;
  return error as AxiosLikeError;
}

/**
 * Retourne un message utilisateur lisible pour n'importe quel type d'erreur :
 * 1. Si le payload backend a un `code` connu : message catalogué (UI-friendly).
 * 2. Sinon, le `message` brut renvoyé par l'API (déjà en français côté back).
 * 3. Sinon, `error.message` (Error JS) ou un fallback générique.
 */
export function getErrorMessage(
  error: unknown,
  fallback = 'Une erreur inattendue est survenue.',
): string {
  const ax = asAxiosLike(error);
  if (ax) {
    const data = ax.response?.data;
    if (data) {
      if (data.code && ERROR_MESSAGES[data.code]) {
        return ERROR_MESSAGES[data.code];
      }
      if (typeof data.message === 'string' && data.message.length > 0) {
        return data.message;
      }
      // Legacy `detail` shape (FastAPI default).
      if (typeof data.detail === 'string' && data.detail.length > 0) {
        return data.detail;
      }
    }
    if (ax.message) return ax.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/** Retourne le code d'erreur (`AUTH_1001`, …) si présent dans la réponse API. */
export function getErrorCode(error: unknown): string | null {
  const ax = asAxiosLike(error);
  if (!ax) return null;
  const code = ax.response?.data?.code;
  return typeof code === 'string' ? code : null;
}

/** Retourne le code HTTP si on peut le déterminer. */
export function getErrorStatus(error: unknown): number | null {
  const ax = asAxiosLike(error);
  return ax?.response?.status ?? null;
}

/** Retourne les `extras` éventuels (champs invalides, retry_after_seconds, …). */
export function getErrorExtras(
  error: unknown,
): Record<string, unknown> | null {
  const ax = asAxiosLike(error);
  const extras = ax?.response?.data?.extras;
  if (extras && typeof extras === 'object') {
    return extras as Record<string, unknown>;
  }
  return null;
}
