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
) -> None:
    recipients = get_emails_by_roles(db, ["Compta", "Super Admin"])
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
) -> None:
    recipients = get_emails_by_roles(db, ["Compta", "Super Admin"])
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


async def send_status_change(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Generic notification used to inform users of status changes."""
    await _send(subject, body, [recipient])
