"""Email sending helpers built on top of fastapi-mail."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Iterable

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud.user import get_emails_by_roles


logger = get_logger("email")


# Ports SMTP a semantique fixe : 465 = TLS implicite (la connexion est chiffree
# des l'ouverture), 587 et 25 = connexion en clair puis STARTTLS.
_IMPLICIT_TLS_PORTS = {465}
_STARTTLS_PORTS = {587, 25}


def _resolve_tls_mode() -> tuple[bool, bool]:
    """Retourne ``(starttls, ssl_implicite)`` en faisant primer le port.

    La configuration livree combinait ``SMTP_PORT=465`` avec
    ``SMTP_USE_TLS=true`` et ``SMTP_USE_SSL=false``, soit un STARTTLS sur un port
    a TLS implicite. La connexion echouait, et comme ``_send`` avale les
    exceptions, plus aucun email ne partait sans que rien ne le signale.

    Le port etant sans ambiguite, on s'aligne dessus et on trace l'ecart.
    """
    starttls = settings.smtp_use_tls and not settings.smtp_use_ssl
    ssl_implicit = settings.smtp_use_ssl

    if settings.smtp_port in _IMPLICIT_TLS_PORTS and not ssl_implicit:
        logger.warning(
            "SMTP_PORT=%d impose un TLS implicite : SMTP_USE_SSL force a true "
            "(corriger le .env : SMTP_USE_SSL=true, SMTP_USE_TLS=false).",
            settings.smtp_port,
        )
        starttls, ssl_implicit = False, True
    elif settings.smtp_port in _STARTTLS_PORTS and ssl_implicit:
        logger.warning(
            "SMTP_PORT=%d attend STARTTLS : SMTP_USE_SSL force a false "
            "(corriger le .env : SMTP_USE_SSL=false, SMTP_USE_TLS=true).",
            settings.smtp_port,
        )
        starttls, ssl_implicit = True, False

    return starttls, ssl_implicit


def _build_config() -> ConnectionConfig | None:
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not configured — emails will be skipped.")
        return None
    starttls, ssl_implicit = _resolve_tls_mode()
    return ConnectionConfig(
        MAIL_USERNAME=settings.smtp_user,
        MAIL_PASSWORD=settings.smtp_password,
        MAIL_FROM=settings.email_from,
        MAIL_FROM_NAME=settings.email_from_name,
        MAIL_PORT=settings.smtp_port,
        MAIL_SERVER=settings.smtp_host,
        MAIL_STARTTLS=starttls,
        MAIL_SSL_TLS=ssl_implicit,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


_config = _build_config()
_mailer = FastMail(_config) if _config else None


async def _send_raw(
    subject: str,
    body: str,
    recipients: Iterable[str],
    *,
    html: bool = False,
    attachments: Sequence[Path] | None = None,
) -> None:
    """Envoi qui **leve** en cas d'echec. Reserve aux envois critiques.

    Utilise par le circuit comptable, ou un echec silencieux signifie qu'une
    piece n'arrive jamais chez le comptable sans que personne ne s'en apercoive
    avant la cloture. Les envois d'agrement (alertes stock, invitations) passent
    par :func:`_send`, qui reste tolerant.
    """
    rec_list = [r for r in recipients if r]
    if not rec_list:
        raise AppException(
            ErrorCode.EMAIL_SEND_FAILED, detail="Aucun destinataire pour cet envoi."
        )
    # Coupe-circuit unique, place avant tout acces au SMTP : le `.env` de
    # developpement pointe sur le serveur de messagerie reel de l'association,
    # et une seance de tests suffit a arroser des destinataires veritables.
    # L'envoi est considere comme reussi, pour que le circuit comptable se
    # deroule jusqu'au bout et reste observable sans quitter le poste.
    if not settings.email_enabled:
        logger.warning(
            "EMAIL_ENABLED=false — envoi supprime (sujet=%r, %d destinataire(s) : %s)",
            subject,
            len(rec_list),
            ", ".join(rec_list),
        )
        return
    if _mailer is None:
        raise AppException(
            ErrorCode.EMAIL_SEND_FAILED,
            detail="Serveur SMTP non configure (SMTP_HOST / SMTP_USER).",
        )

    message = MessageSchema(
        subject=subject,
        recipients=rec_list,
        body=body,
        subtype=MessageType.html if html else MessageType.plain,
        # fastapi-mail nomme la piece jointe d'apres le fichier sur disque :
        # c'est pourquoi les PDF sont copies sous leur nom definitif en amont.
        attachments=[str(p) for p in (attachments or [])],
    )
    try:
        await _mailer.send_message(message)
    except Exception as exc:  # noqa: BLE001 — aiosmtplib leve des types varies
        logger.exception("Echec envoi email '%s' : %s", subject, exc)
        raise AppException(
            ErrorCode.EMAIL_SEND_FAILED,
            detail="L'envoi du courriel a echoue.",
            extras={"reason": str(exc)[:300]},
        ) from exc
    logger.info(
        "Email envoye a %d destinataire(s) (sujet=%r, %d piece(s) jointe(s))",
        len(rec_list),
        subject,
        len(attachments or []),
    )


async def _send(subject: str, body: str, recipients: Iterable[str], html: bool = False) -> None:
    """Envoi best-effort : un echec est journalise, jamais propage.

    Conserve tel quel pour les notifications non critiques (alertes de stock,
    changements de statut, invitations) : les appelants n'ont pas de strategie
    de reprise et ne doivent pas faire echouer la requete de l'utilisateur.
    """
    rec_list = [r for r in recipients if r]
    if not rec_list:
        logger.info("No recipients for subject=%r — skipping send.", subject)
        return
    if _mailer is None:
        logger.warning("Mailer not configured — skipping send to %s", rec_list)
        return
    try:
        await _send_raw(subject, body, rec_list, html=html)
    except AppException:
        pass  # deja journalise par _send_raw



def _destinataires_sauf_auteur(
    db: Session, roles: list[str], auteur_email: str | None
) -> list[str]:
    """Destinataires d'une notification, l'auteur de l'action exclu.

    Sur une petite structure, la meme personne cumule les roles : le seul compte
    disposant d'une adresse est aussi celui qui depose. Sans cette exclusion,
    deposer une facture declenche un courriel annoncant a son auteur qu'une
    facture vient d'etre deposee — du bruit qui finit par masquer les
    notifications utiles.
    """
    destinataires = get_emails_by_roles(db, roles)
    if not auteur_email:
        return destinataires
    reference = auteur_email.strip().lower()
    return [e for e in destinataires if e.strip().lower() != reference]


async def send_stock_alert(
    db: Session,
    *,
    item_name: str,
    quantity: int,
    threshold: int,
) -> None:
    recipients = get_emails_by_roles(db, ["AdminBenevoles", "Super Admin"])
    subject = f"Alerte stock bas : {item_name}"
    body = (
        "Bonjour,\n\n"
        "Ceci est une alerte automatique de l'application de gestion de stock.\n\n"
        f"Article : {item_name}\n"
        f"Quantite restante : {quantity}\n"
        f"Seuil d'alerte : {threshold}\n\n"
        "Merci de prevoir un reapprovisionnement.\n\n"
        "Cordialement,\nVotre systeme de gestion de stock."
    )
    await _send(subject, body, recipients)


async def send_buvette_low_stock_alert(
    db: Session,
    *,
    product_name: str,
    quantity: int,
    threshold: int,
) -> None:
    recipients = get_emails_by_roles(db, ["AdminBenevoles", "Super Admin"])
    subject = f"Alerte stock buvette : {product_name}"
    body = (
        "Bonjour,\n\n"
        "Ceci est une alerte automatique de la buvette.\n\n"
        f"Produit : {product_name}\n"
        f"Quantite restante : {quantity}\n"
        f"Seuil d'alerte : {threshold}\n\n"
        "Merci de prevoir un reapprovisionnement avant la prochaine vente HelloAsso.\n\n"
        "Cordialement,\nVotre systeme de gestion de stock."
    )
    await _send(subject, body, recipients)


async def send_new_expense_notification(
    db: Session,
    *,
    user_full_name: str,
    amount: float,
    rattachement: str | None,
    auteur_email: str | None = None,
) -> None:
    recipients = _destinataires_sauf_auteur(db, ["Compta", "Super Admin"], auteur_email)
    if not recipients:
        return
    subject = f"Nouvelle note de frais soumise par {user_full_name}"
    body = (
        "Bonjour,\n\n"
        "Une nouvelle note de frais a ete soumise et est en attente de validation.\n\n"
        f"Soumis par : {user_full_name}\n"
        f"Montant : {amount:.2f} EUR\n"
        f"Rattachement : {rattachement or '-'}\n\n"
        "Vous pouvez la consulter et la valider dans l'application.\n\n"
        "Cordialement,\nVotre systeme de gestion."
    )
    await _send(subject, body, recipients)


async def send_invoice_notification(
    db: Session,
    *,
    user_full_name: str,
    comment: str | None,
    auteur_email: str | None = None,
) -> None:
    recipients = _destinataires_sauf_auteur(db, ["Compta", "Super Admin"], auteur_email)
    if not recipients:
        return
    subject = f"Nouveau depot de facture par {user_full_name}"
    body = (
        "Bonjour,\n\n"
        "Un nouveau depot de facture a ete effectue.\n\n"
        f"Depose par : {user_full_name}\n"
        f"Commentaire : {comment or 'Aucun'}\n\n"
        "Connectez-vous a l'application pour la consulter.\n\n"
        "Cordialement,\nVotre systeme de gestion."
    )
    await _send(subject, body, recipients)


async def send_admin_invitation(
    *,
    email: str,
    invitation_url: str,
    expires_at: str,
) -> None:
    subject = "Invitation administrateur — Le Kouttab"
    body = (
        "Bonjour,\n\n"
        "Vous avez ete invite(e) a creer un compte administrateur sur l'application "
        "de gestion de stock du Kouttab.\n\n"
        f"Cliquez sur ce lien pour finaliser votre inscription : {invitation_url}\n\n"
        f"Le lien est valide jusqu'au {expires_at}.\n\n"
        "Si vous n'etes pas a l'origine de cette demande, ignorez ce message.\n\n"
        "Cordialement,\nLe Kouttab."
    )
    await _send(subject, body, [email])


async def send_password_reset(
    *,
    email: str,
    reset_url: str,
    expires_at: str,
) -> None:
    """Lien de reinitialisation, a usage unique.

    Le message rappelle que le mot de passe actuel reste valable tant que le
    lien n'a pas ete ouvert : sans cette precision, une demande faite par erreur
    laisse croire que le compte est deja inaccessible.
    """
    subject = "Reinitialisation de votre mot de passe — Le Kouttab"
    body = (
        "Bonjour,\n\n"
        "Une reinitialisation de mot de passe a ete demandee pour votre compte "
        "sur l'application de gestion de stock du Kouttab.\n\n"
        f"Cliquez sur ce lien pour choisir un nouveau mot de passe : {reset_url}\n\n"
        f"Ce lien est valable jusqu'au {expires_at} et ne fonctionne qu'une fois.\n\n"
        "Si vous n'etes pas a l'origine de cette demande, ignorez ce message : "
        "votre mot de passe actuel reste valable et rien n'a ete modifie.\n\n"
        "Cordialement,\nLe Kouttab."
    )
    await _send(subject, body, [email])


def doit_notifier_du_statut(recipient: str, auteur_email: str | None) -> bool:
    """Faux quand le valideur est aussi le destinataire.

    Il vient de faire l'action : lui ecrire pour la lui annoncer n'apprend rien
    et noie les notifications utiles. Fonction separee de l'envoi pour rester
    verifiable — la fixture de test remplace `send_status_change` en entier.
    """
    if not auteur_email:
        return True
    return recipient.strip().lower() != auteur_email.strip().lower()


async def send_status_change(
    *,
    recipient: str,
    subject: str,
    body: str,
    auteur_email: str | None = None,
) -> None:
    """Informe le deposant d'un changement de statut."""
    if not doit_notifier_du_statut(recipient, auteur_email):
        return
    await _send(subject, body, [recipient])


async def send_justificatif_reminder(
    *,
    recipient: str,
    prenom: str | None,
    libelle: str,
    description: str | None = None,
    montant: str | None = None,
    date_achat: str | None = None,
    fournisseur: str | None = None,
    rappel_numero: int,
    rappels_max: int,
) -> None:
    """Relance un benevole pour un justificatif manquant.

    Le message ne mentionne que ce que la comptabilite a renseigne : un ticket
    ouvert avec le seul libelle produit un rappel court plutot qu'un formulaire
    a trous, qui donnerait l'impression d'un envoi automatique mal configure.

    Passe par :func:`_send` (best-effort) et non `_send_raw` : un rappel perdu
    se rattrape au tour suivant, il n'a pas la criticite d'une piece comptable.
    """
    salutation = f"Bonjour {prenom}," if prenom else "Bonjour,"
    details = [f"Objet         : {libelle}"]
    if montant:
        details.append(f"Montant       : {montant}")
    if date_achat:
        details.append(f"Date d'achat  : {date_achat}")
    if fournisseur:
        details.append(f"Fournisseur   : {fournisseur}")
    if description:
        details.append(f"Precision     : {description}")

    # Le dernier rappel le dit : sans cela, le silence qui suit passerait pour
    # un oubli de l'application plutot que pour la fin des relances.
    cloture = (
        "\n\nC'est le dernier rappel automatique pour cette demande ; "
        "la comptabilite reprendra contact si besoin."
        if rappel_numero >= rappels_max
        else ""
    )

    body = (
        f"{salutation}\n\n"
        "Un justificatif d'achat manque a la comptabilite de l'association.\n\n"
        + "\n".join(details)
        + "\n\nMerci de le deposer dans l'application, rubrique « Depot de "
        "factures ». Si vous l'avez deja transmis, ignorez ce message."
        + cloture
        + "\n\nCordialement,\nLe Kouttab — gestion des stocks."
    )
    await _send(f"[Justificatif attendu] {libelle}", body, [recipient])


async def send_new_account_request(
    db: Session,
    *,
    username: str,
    full_name: str,
    email: str | None,
) -> None:
    """Previent les Super Admins qu'un compte attend une validation.

    Sans cet envoi, une demande d'inscription restait invisible jusqu'a ce qu'un
    Super Admin pense a ouvrir l'ecran d'administration : le demandeur pouvait
    attendre plusieurs jours sans que personne ne le sache.
    """
    destinataires = get_emails_by_roles(db, ["Super Admin"])
    if not destinataires:
        logger.warning(
            "Demande de compte %r : aucun Super Admin avec une adresse e-mail.", username
        )
        return

    await _send(
        "Nouvelle demande de creation de compte",
        (
            "Bonjour,\n\n"
            f"{full_name or username} demande la creation d'un compte.\n"
            f"Identifiant : {username}\n"
            f"Adresse e-mail : {email or 'non renseignee'}\n\n"
            "La demande est en attente dans Administration > Comptes a valider.\n\n"
            "Cordialement,\nLe Kouttab."
        ),
        destinataires,
    )
