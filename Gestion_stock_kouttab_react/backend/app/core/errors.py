"""Centralised error catalogue (codes + HTTP status + French messages).

Every business error raised by the API uses one of the codes defined here so that
the frontend can map it to a user-friendly message and so that support / logs can
trace any incident back to a single identifier.

Usage::

    from app.core.errors import ErrorCode
    from app.core.exceptions import AppException

    raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)
    raise AppException(ErrorCode.INVALID_AMOUNT, detail="Le montant doit etre > 0.")
    raise AppException(
        ErrorCode.VALIDATION_ERROR,
        extras={"fields": ["nom", "email"]},
    )

To add a new code:
1. Add an entry in :class:`ErrorCode` (use the matching family prefix).
2. Add the (status, message) tuple in :data:`ERROR_MESSAGES`.
3. Mirror the code in ``frontend/src/lib/errors.ts``.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Application-wide error code catalogue."""

    # ---- Auth (1xxx) -------------------------------------------------------
    INVALID_CREDENTIALS = "AUTH_1001"
    ACCOUNT_PENDING = "AUTH_1002"
    ACCOUNT_REJECTED = "AUTH_1003"
    ACCOUNT_LOCKED = "AUTH_1004"
    TOKEN_EXPIRED = "AUTH_1010"
    TOKEN_INVALID = "AUTH_1011"
    TOKEN_MISSING = "AUTH_1012"
    REFRESH_TOKEN_INVALID = "AUTH_1013"
    PASSWORD_WEAK = "AUTH_1020"
    PASSWORD_MUST_CHANGE = "AUTH_1021"
    USERNAME_INVALID = "AUTH_1022"
    USERNAME_TAKEN = "AUTH_1023"
    EMAIL_INVALID = "AUTH_1024"
    EMAIL_TAKEN = "AUTH_1025"
    INVITATION_INVALID = "AUTH_1030"
    INVITATION_EXPIRED = "AUTH_1031"
    INVITATION_USED = "AUTH_1032"
    INVITATION_TOO_MANY_ATTEMPTS = "AUTH_1033"

    # ---- Permissions (2xxx) ------------------------------------------------
    FORBIDDEN = "PERM_2001"
    ROLE_REQUIRED = "PERM_2002"
    SELF_ACTION_FORBIDDEN = "PERM_2003"

    # ---- Resources (3xxx) --------------------------------------------------
    NOT_FOUND = "RES_3001"
    USER_NOT_FOUND = "RES_3002"
    STOCK_ITEM_NOT_FOUND = "RES_3003"
    EXPENSE_NOT_FOUND = "RES_3004"
    INVOICE_NOT_FOUND = "RES_3005"
    CATEGORY_NOT_FOUND = "RES_3006"
    SUBCATEGORY_NOT_FOUND = "RES_3007"
    BUVETTE_PRODUCT_NOT_FOUND = "RES_3008"
    INVITATION_NOT_FOUND = "RES_3009"
    FILE_NOT_FOUND = "RES_3010"
    MODIFICATION_NOT_FOUND = "RES_3011"

    # ---- Conflicts (4xxx) --------------------------------------------------
    CONFLICT = "CONF_4001"
    STOCK_ITEM_DUPLICATE = "CONF_4002"
    CATEGORY_HAS_ITEMS = "CONF_4003"
    SUBCATEGORY_HAS_ITEMS = "CONF_4004"
    EXPENSE_NOT_EDITABLE = "CONF_4005"
    EXPENSE_NOT_DELETABLE = "CONF_4006"
    USER_HAS_DEPENDENCIES = "CONF_4007"
    CATEGORY_DUPLICATE = "CONF_4008"
    SUBCATEGORY_DUPLICATE = "CONF_4009"
    MODIFICATION_NOT_PENDING = "CONF_4010"
    BARCODE_DUPLICATE = "CONF_4011"

    # ---- Validation (5xxx) -------------------------------------------------
    VALIDATION_ERROR = "VAL_5001"
    REQUIRED_FIELD_MISSING = "VAL_5002"
    INVALID_AMOUNT = "VAL_5003"
    INVALID_QUANTITY = "VAL_5004"
    INVALID_DATE = "VAL_5005"
    INVALID_FILE_TYPE = "VAL_5006"
    FILE_TOO_LARGE = "VAL_5007"
    TOO_MANY_FILES = "VAL_5008"
    CSV_FORMAT_INVALID = "VAL_5009"
    FILE_PHYSICALLY_MISSING = "VAL_5010"
    BARCODE_INVALID = "VAL_5011"

    # ---- External services (6xxx) -----------------------------------------
    HELLOASSO_AUTH_FAILED = "EXT_6001"
    HELLOASSO_API_ERROR = "EXT_6002"
    HELLOASSO_WEBHOOK_INVALID = "EXT_6003"
    HELLOASSO_NOT_CONFIGURED = "EXT_6004"
    EMAIL_SEND_FAILED = "EXT_6010"
    DATABASE_ERROR = "EXT_6020"
    OPENFOODFACTS_UNAVAILABLE = "EXT_6030"

    # ---- Rate limit (7xxx) ------------------------------------------------
    RATE_LIMIT_EXCEEDED = "RATE_7001"
    LOGIN_RATE_LIMITED = "RATE_7002"

    # ---- Generic (9xxx) ---------------------------------------------------
    INTERNAL_ERROR = "GEN_9001"
    SERVICE_UNAVAILABLE = "GEN_9002"
    BAD_REQUEST = "GEN_9003"


# Mapping ErrorCode -> (HTTP status, message FR).
ERROR_MESSAGES: dict[ErrorCode, tuple[int, str]] = {
    # Auth
    ErrorCode.INVALID_CREDENTIALS: (401, "Identifiants incorrects."),
    ErrorCode.ACCOUNT_PENDING: (
        403,
        "Votre compte est en attente de validation par un administrateur.",
    ),
    ErrorCode.ACCOUNT_REJECTED: (
        403,
        "Votre compte a ete refuse. Contactez un administrateur.",
    ),
    ErrorCode.ACCOUNT_LOCKED: (
        429,
        "Compte temporairement verrouille apres trop de tentatives. "
        "Reessayez dans quelques minutes.",
    ),
    ErrorCode.TOKEN_EXPIRED: (401, "Votre session a expire, veuillez vous reconnecter."),
    ErrorCode.TOKEN_INVALID: (401, "Token d'authentification invalide."),
    ErrorCode.TOKEN_MISSING: (401, "Authentification requise."),
    ErrorCode.REFRESH_TOKEN_INVALID: (
        401,
        "Le jeton de rafraichissement est invalide ou expire.",
    ),
    ErrorCode.PASSWORD_WEAK: (
        400,
        "Le mot de passe doit contenir au moins 8 caracteres, une majuscule, "
        "une minuscule, un chiffre et un caractere special.",
    ),
    ErrorCode.PASSWORD_MUST_CHANGE: (
        200,
        "Vous devez changer votre mot de passe avant de continuer.",
    ),
    ErrorCode.USERNAME_INVALID: (
        400,
        "Nom d'utilisateur invalide (3-20 caracteres, lettres/chiffres/_).",
    ),
    ErrorCode.USERNAME_TAKEN: (409, "Ce nom d'utilisateur est deja pris."),
    ErrorCode.EMAIL_INVALID: (400, "Adresse email invalide."),
    ErrorCode.EMAIL_TAKEN: (409, "Cette adresse email est deja utilisee."),
    ErrorCode.INVITATION_INVALID: (400, "Lien d'invitation invalide."),
    ErrorCode.INVITATION_EXPIRED: (
        400,
        "Lien d'invitation expire. Demandez-en un nouveau a votre administrateur.",
    ),
    ErrorCode.INVITATION_USED: (400, "Ce lien d'invitation a deja ete utilise."),
    ErrorCode.INVITATION_TOO_MANY_ATTEMPTS: (
        400,
        "Trop de tentatives sur cette invitation. Demandez-en une nouvelle.",
    ),

    # Permissions
    ErrorCode.FORBIDDEN: (
        403,
        "Vous n'avez pas les droits necessaires pour effectuer cette action.",
    ),
    ErrorCode.ROLE_REQUIRED: (403, "Cette action necessite un role specifique."),
    ErrorCode.SELF_ACTION_FORBIDDEN: (
        403,
        "Vous ne pouvez pas effectuer cette action sur votre propre compte.",
    ),

    # Resources
    ErrorCode.NOT_FOUND: (404, "Ressource introuvable."),
    ErrorCode.USER_NOT_FOUND: (404, "Utilisateur introuvable."),
    ErrorCode.STOCK_ITEM_NOT_FOUND: (404, "Article introuvable."),
    ErrorCode.EXPENSE_NOT_FOUND: (404, "Note de frais introuvable."),
    ErrorCode.INVOICE_NOT_FOUND: (404, "Facture introuvable."),
    ErrorCode.CATEGORY_NOT_FOUND: (404, "Categorie introuvable."),
    ErrorCode.SUBCATEGORY_NOT_FOUND: (404, "Sous-categorie introuvable."),
    ErrorCode.BUVETTE_PRODUCT_NOT_FOUND: (404, "Produit de la buvette introuvable."),
    ErrorCode.INVITATION_NOT_FOUND: (404, "Invitation introuvable."),
    ErrorCode.FILE_NOT_FOUND: (404, "Fichier introuvable."),
    ErrorCode.MODIFICATION_NOT_FOUND: (404, "Demande de modification introuvable."),

    # Conflicts
    ErrorCode.CONFLICT: (409, "Conflit avec une ressource existante."),
    ErrorCode.STOCK_ITEM_DUPLICATE: (409, "Un article avec ce nom existe deja."),
    ErrorCode.CATEGORY_HAS_ITEMS: (
        409,
        "Cette categorie contient encore des articles. "
        "Deplacez-les avant de la supprimer.",
    ),
    ErrorCode.SUBCATEGORY_HAS_ITEMS: (
        409,
        "Cette sous-categorie contient encore des articles.",
    ),
    ErrorCode.EXPENSE_NOT_EDITABLE: (
        409,
        "Cette note de frais ne peut plus etre modifiee "
        "(statut different de \"En attente\").",
    ),
    ErrorCode.EXPENSE_NOT_DELETABLE: (
        409,
        "Seules les notes au statut \"Remboursee\" peuvent etre supprimees.",
    ),
    ErrorCode.USER_HAS_DEPENDENCIES: (
        409,
        "Cet utilisateur a des notes ou factures liees. Action impossible.",
    ),
    ErrorCode.CATEGORY_DUPLICATE: (409, "Cette categorie existe deja."),
    ErrorCode.SUBCATEGORY_DUPLICATE: (409, "Cette sous-categorie existe deja."),
    ErrorCode.MODIFICATION_NOT_PENDING: (
        409,
        "Cette demande de modification n'est plus en attente.",
    ),
    ErrorCode.BARCODE_DUPLICATE: (
        409,
        "Ce code-barres est deja associe a un autre article.",
    ),

    # Validation
    ErrorCode.VALIDATION_ERROR: (422, "Donnees invalides."),
    ErrorCode.REQUIRED_FIELD_MISSING: (
        422,
        "Un ou plusieurs champs obligatoires sont manquants.",
    ),
    ErrorCode.INVALID_AMOUNT: (422, "Montant invalide (doit etre positif)."),
    ErrorCode.INVALID_QUANTITY: (
        422,
        "Quantite invalide (doit etre un entier positif).",
    ),
    ErrorCode.INVALID_DATE: (422, "Date invalide."),
    ErrorCode.INVALID_FILE_TYPE: (415, "Type de fichier non autorise."),
    ErrorCode.FILE_TOO_LARGE: (413, "Fichier trop volumineux (10 Mo maximum)."),
    ErrorCode.TOO_MANY_FILES: (413, "Trop de fichiers (5 maximum par envoi)."),
    ErrorCode.CSV_FORMAT_INVALID: (
        422,
        "Format CSV invalide. Verifiez les colonnes attendues.",
    ),
    ErrorCode.FILE_PHYSICALLY_MISSING: (
        410,
        "Le fichier n'est plus disponible sur le serveur.",
    ),
    ErrorCode.BARCODE_INVALID: (
        422,
        "Code-barres invalide (8 a 14 chiffres attendus).",
    ),

    # External
    ErrorCode.HELLOASSO_AUTH_FAILED: (
        502,
        "Authentification HelloAsso echouee. Verifiez les credentials dans les parametres.",
    ),
    ErrorCode.HELLOASSO_API_ERROR: (
        502,
        "Erreur lors de l'appel a HelloAsso. Reessayez plus tard.",
    ),
    ErrorCode.HELLOASSO_WEBHOOK_INVALID: (
        200,
        "Payload webhook ignore (format inattendu).",
    ),
    ErrorCode.HELLOASSO_NOT_CONFIGURED: (
        503,
        "L'integration HelloAsso n'est pas configuree.",
    ),
    ErrorCode.EMAIL_SEND_FAILED: (
        502,
        "L'envoi de l'email a echoue. L'action a quand meme ete enregistree.",
    ),
    ErrorCode.DATABASE_ERROR: (500, "Erreur base de donnees. Contactez l'administrateur."),
    ErrorCode.OPENFOODFACTS_UNAVAILABLE: (
        503,
        "Le service OpenFoodFacts est temporairement indisponible.",
    ),

    # Rate limit
    ErrorCode.RATE_LIMIT_EXCEEDED: (429, "Trop de requetes. Patientez quelques instants."),
    ErrorCode.LOGIN_RATE_LIMITED: (
        429,
        "Trop de tentatives de connexion. Reessayez dans 15 minutes.",
    ),

    # Generic
    ErrorCode.INTERNAL_ERROR: (500, "Erreur interne du serveur."),
    ErrorCode.SERVICE_UNAVAILABLE: (503, "Service temporairement indisponible."),
    ErrorCode.BAD_REQUEST: (400, "Requete invalide."),
}


def get_status_and_message(code: ErrorCode) -> tuple[int, str]:
    """Return ``(http_status, default_message)`` for the given code."""
    return ERROR_MESSAGES[code]


__all__ = ["ErrorCode", "ERROR_MESSAGES", "get_status_and_message"]
