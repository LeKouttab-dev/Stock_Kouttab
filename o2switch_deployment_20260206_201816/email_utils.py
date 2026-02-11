import streamlit as st
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from logger_config import logger

def get_email_config():
    """Récupère la configuration email depuis les variables d'environnement (production) ou secrets (développement)"""
    # En production, utilise les variables d'environnement O2Switch
    if os.environ.get('ENVIRONMENT') == 'production':
        return {
            'sender_email': os.environ.get('EMAIL_SENDER', 'no-reply@lekouttab.fr'),
            'sender_password': os.environ.get('EMAIL_PASSWORD'),
            'smtp_server': os.environ.get('EMAIL_SMTP', 'mail.lekouttab.fr'),
            'smtp_port': int(os.environ.get('EMAIL_PORT', '465')),
            'use_tls': True
        }
    else:
        # Mode développement : essayer les secrets Streamlit (si disponibles)
        try:
            return {
                'sender_email': st.secrets["email_credentials"]["sender_email"],
                'sender_password': st.secrets["email_credentials"]["sender_password"],
                'smtp_server': st.secrets["email_credentials"]["smtp_server"],
                'smtp_port': st.secrets["email_credentials"]["smtp_port"],
                'use_tls': st.secrets["email_credentials"].get("use_tls", True)
            }
        except (KeyError, FileNotFoundError):
            # Si pas de secrets, utilisez des valeurs par défaut pour le développement
            st.warning("⚠️ Mode développement : Configurez les emails dans .streamlit/secrets.toml ou utilisez les variables d'environnement")
            return {
                'sender_email': 'dev-test@lekouttab.fr',
                'sender_password': 'dev_password',
                'smtp_server': 'localhost',
                'smtp_port': 587,
                'use_tls': False
            }

def send_alert_email(item_name, current_quantity, alert_threshold, recipient_emails):
    """
    Envoie un e-mail d'alerte de stock bas.
    """
    if not recipient_emails:
        st.warning("Aucun destinataire trouvé pour l'alerte e-mail.")
        return

    email_config = get_email_config()
    if not email_config:
        return

    try:
        # Configuration O2Switch
        sender_email = email_config['sender_email']
        sender_password = email_config['sender_password']
        smtp_server = email_config['smtp_server']
        smtp_port = email_config['smtp_port']
        use_tls = email_config['use_tls']
    except (KeyError, FileNotFoundError):
        st.error("Les informations d'identification pour l'envoi d'e-mails ne sont pas configurées dans secrets.toml.")
        return

    # Création du message
    subject = f"Alerte de Stock Bas : {item_name}"
    body = f"""
    Bonjour,

    Ceci est une alerte automatique de l'application de gestion de stock.
    
    L'article suivant a atteint un niveau de stock critique :
    
    - Article : {item_name}
    - Quantité restante : {current_quantity}
    - Seuil d'alerte : {alert_threshold}
    
    Veuillez s'il vous plaît prévoir un réapprovisionnement.
    
    Cordialement,
    Votre système de Gestion de Stock
    """

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = ", ".join(recipient_emails)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        # Connexion au serveur SMTP O2Switch
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        if use_tls:
            # Pour O2Switch avec port 465
            context = smtplib.ssl.create_default_context()
            server.starttls(context=context)
        
        server.login(sender_email, sender_password)
        
        # Envoi de l'e-mail
        server.sendmail(sender_email, recipient_emails, message.as_string())
        
        server.quit()
        logger.info(f"Alerte e-mail envoyée avec succès pour {item_name}.")
        print(f"✅ Alert e-mail envoyé pour {item_name}")

    except smtplib.SMTPAuthenticationError:
        st.error("❌ Erreur d'authentification SMTP. Vérifiez votre email et mot de passe O2Switch.")
        logger.error(f"Erreur SMTP: Échec authentification pour {sender_email}")
    except Exception as e:
        st.error(f"❌ Une erreur est survenue lors de l'envoi de l'e-mail : {e}")
        logger.error(f"Erreur SMTP: {e}")
        print(f"❌ Erreur SMTP : {e}")

def send_new_expense_alert_email(user_name, amount, reason, recipient_emails):
    """Envoie un e-mail pour une nouvelle note de frais."""
    if not recipient_emails:
        st.warning("Aucun destinataire (Compta/Super Admin) trouvé pour l'alerte de note de frais.")
        return

    email_config = get_email_config()
    if not email_config:
        return

    subject = f"Nouvelle Note de Frais Soumise par {user_name}"
    body = f"""
    Bonjour,

    Une nouvelle note de frais a été soumise et est en attente de validation.
    
    - Soumis par : {user_name}
    - Montant : {amount:.2f} €
    - Rattachement : {reason}
    
    Vous pouvez la consulter et la valider dans le dashboard des notes de frais de l'application.
    
    Cordialement,
    Votre système de Gestion
    """

    message = MIMEMultipart()
    message["From"] = email_config['sender_email']
    message["To"] = ", ".join(recipient_emails)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        # Connexion au serveur SMTP O2Switch
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        
        if email_config['use_tls']:
            # Pour O2Switch avec port 465
            context = smtplib.ssl.create_default_context()
            server.starttls(context=context)
        
        server.login(email_config['sender_email'], email_config['sender_password'])
        server.sendmail(email_config['sender_email'], recipient_emails, message.as_string())
        server.quit()
        logger.info(f"Alerte e-mail pour nouvelle note de frais envoyée par {user_name}.")
        print(f"✅ Alert email sent for new expense by {user_name}")
    except smtplib.SMTPAuthenticationError:
        st.error("❌ Erreur d'authentification SMTP. Vérifiez votre email et mot de passe O2Switch.")
        logger.error(f"Erreur SMTP: Échec authentification pour {email_config['sender_email']}")
    except Exception as e:
        st.error(f"❌ Une erreur est survenue lors de l'envoi de l'e-mail : {e}")
        logger.error(f"Erreur SMTP: {e}")
        print(f"❌ Erreur SMTP : {e}")

def send_invoice_email(user_name, comment, files, recipient_emails):
    """Envoie un e-mail avec des factures en pièces jointes."""
    if not recipient_emails:
        logger.warning("Tentative d'envoi de facture sans destinataire.")
        st.warning("Aucun destinataire (Compta/Super Admin) n'a été trouvé pour recevoir les factures.")
        return

    try:
        sender_email = st.secrets["email_credentials"]["sender_email"]
        sender_password = st.secrets["email_credentials"]["sender_password"]
    except (KeyError, FileNotFoundError):
        logger.error("Les informations d'identification pour l'envoi d'e-mails ne sont pas configurées dans secrets.toml.")
        st.error("Les informations d'identification pour l'envoi d'e-mails ne sont pas configurées dans secrets.toml.")
        return

    subject = f"Nouveau Dépôt de Facture par {user_name}"
    body = f"""
    Bonjour,
    Un nouveau dépôt de facture a été effectué.

    - Déposé par : {user_name}
    - Commentaire : {comment if comment else "Aucun commentaire"}

    Vous trouverez la ou les facture(s) en pièces jointes de cet e-mail.

    Cordialement,
    Votre système de Gestion
    """

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = ", ".join(recipient_emails)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    for file in files:
        try:
            file.seek(0) # S'assurer que le pointeur est au début du fichier
            part = MIMEApplication(file.getvalue(), Name=file.name)
            part['Content-Disposition'] = f'attachment; filename="{file.name}"'
            message.attach(part)
            logger.info(f"Fichier '{file.name}' attaché à l'e-mail de facture.")
        except Exception as e:
            logger.error(f"Erreur lors de l'attachement du fichier {file.name}: {e}")
            st.error(f"Impossible d'attacher le fichier {file.name}.")

    try:
        # Connexion au serveur SMTP O2Switch
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        if use_tls:
            # Pour O2Switch avec port 465
            context = smtplib.ssl.create_default_context()
            server.starttls(context=context)
        
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_emails, message.as_string())
        server.quit()
        logger.info(f"Facture email envoyé par {user_name} avec {len(files)} fichier(s).")
        print(f"✅ Invoice email sent by {user_name} with {len(files)} file(s)")
    except smtplib.SMTPAuthenticationError:
        st.error("❌ Erreur d'authentification SMTP. Vérifiez votre email et mot de passe O2Switch.")
        logger.error(f"Erreur SMTP: Échec authentification pour {sender_email}")
    except Exception as e:
        st.error(f"❌ Une erreur est survenue lors de l'envoi de l'e-mail : {e}")
        logger.error(f"Erreur SMTP: {e}")
        print(f"❌ Erreur SMTP : {e}")
