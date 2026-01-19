import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert_email(item_name, current_quantity, alert_threshold, recipient_emails):
    """
    Envoie un e-mail d'alerte de stock bas.
    """
    if not recipient_emails:
        st.warning("Aucun destinataire trouvé pour l'alerte e-mail.")
        return

    try:
        # Récupérer les identifiants depuis les secrets de Streamlit
        sender_email = st.secrets["email_credentials"]["sender_email"]
        sender_password = st.secrets["email_credentials"]["sender_password"]
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
        # Connexion au serveur SMTP (exemple pour Gmail)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Activer la sécurité
        server.login(sender_email, sender_password)
        
        # Envoi de l'e-mail
        server.sendmail(sender_email, recipient_emails, message.as_string())
        
        server.quit()
        print(f"Alerte e-mail envoyée avec succès pour {item_name}.")

    except smtplib.SMTPAuthenticationError:
        st.error("Erreur d'authentification SMTP. Vérifiez votre e-mail et mot de passe d'application dans secrets.toml.")
    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'envoi de l'e-mail : {e}")
        print(f"Erreur SMTP : {e}")
