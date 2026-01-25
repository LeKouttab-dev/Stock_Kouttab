import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logger_config import logger
from invitation_manager import invitation_manager

def send_admin_invitation_email(admin_email, invitation_link):
    """Envoie un email d'invitation pour le premier admin"""
    
    try:
        # Récupérer les identifiants depuis les secrets
        sender_email = st.secrets["email_credentials"]["sender_email"]
        sender_password = st.secrets["email_credentials"]["sender_password"]
        admin_email_config = st.secrets.get("admin_setup", {}).get("sender_email_admin", sender_email)
        
    except (KeyError, FileNotFoundError):
        logger.error("Configuration email manquante dans secrets.toml")
        return False
    
    subject = "🔐 Invitation à configurer l'administration - Gestion Le Kouttâb"
    
    body = f"""
    Bonjour,
    
    Vous avez été invité à configurer le compte administrateur principal pour l'application 
    de gestion "Gestion Le Kouttâb".
    
    🔗 **Lien de configuration sécurisé :**
    {invitation_link}
    
    ⏰ **Ce lien expirera dans 24 heures**
    
    📋 **Instructions :**
    1. Cliquez sur le lien ci-dessus
    2. Choisissez votre nom d'utilisateur et mot de passe
    3. Votre compte sera automatiquement créé avec les droits "Super Admin"
    
    ⚠️ **Important :** 
    - Ne partagez jamais ce lien
    - Choisissez un mot de passe fort (minimum 8 caractères, mélange de majuscules, minuscules, chiffres et symboles)
    - Ce lien est à usage unique
    
    Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
    
    Cordialement,
    Système de Gestion Le Kouttâb
    """
    
    message = MIMEMultipart()
    message["From"] = admin_email_config
    message["To"] = admin_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    
    try:
        # Configuration SMTP (Gmail par défaut)
        smtp_server = st.secrets.get("smtp", {}).get("server", "smtp.gmail.com")
        smtp_port = st.secrets.get("smtp", {}).get("port", 587)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        server.sendmail(admin_email_config, admin_email, message.as_string())
        server.quit()
        
        logger.info(f"Email d'invitation envoyé à {admin_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email d'invitation: {e}")
        return False

def generate_invitation_url(token, email):
    """Génère l'URL complète d'invitation"""
    base_url = st.secrets.get("app", {}).get("base_url", "http://localhost:8501")
    return f"{base_url}?setup_admin=true&token={token}&email={email}"

def check_admin_setup_mode():
    """Vérifie si on est en mode setup admin"""
    query_params = st.query_params
    return (
        query_params.get("setup_admin") == "true" and
        "token" in query_params and
        "email" in query_params
    )

def display_admin_setup_page():
    """Affiche la page de configuration admin"""
    query_params = st.query_params
    token = query_params.get("token")
    email = query_params.get("email")
    
    st.title("🔐 Configuration du Compte Administrateur")
    st.write(f"Configuration pour : **{email}**")
    
    # Valider le token
    is_valid, message = invitation_manager.validate_invitation_token(token, email)
    
    if not is_valid:
        st.error(f"❌ {message}")
        st.stop()
    
    with st.form("admin_setup_form"):
        st.subheader("Création de votre compte Super Admin")
        
        username = st.text_input(
            "Nom d'utilisateur*", 
            help="3-20 caractères, lettres, chiffres et underscore uniquement"
        )
        
        password = st.text_input(
            "Mot de passe*", 
            type="password",
            help="Minimum 8 caractères, incluez majuscules, minuscules, chiffres et symboles"
        )
        
        password_confirm = st.text_input("Confirmer le mot de passe*", type="password")
        
        # Validation du mot de passe
        password_valid = True
        password_errors = []
        
        if password:
            if len(password) < 8:
                password_valid = False
                password_errors.append("Minimum 8 caractères")
            if not any(c.isupper() for c in password):
                password_valid = False
                password_errors.append("Au moins une majuscule")
            if not any(c.islower() for c in password):
                password_valid = False
                password_errors.append("Au moins une minuscule")
            if not any(c.isdigit() for c in password):
                password_valid = False
                password_errors.append("Au moins un chiffre")
            if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                password_valid = False
                password_errors.append("Au moins un symbole")
        
        if password and password_confirm and password != password_confirm:
            password_valid = False
            password_errors.append("Les mots de passe ne correspondent pas")
        
        if not password_valid and password_errors:
            st.error("❌ " + " | ".join(password_errors))
        
        submitted = st.form_submit_button("🚀 Créer mon compte administrateur", type="primary")
        
        if submitted:
            if not username or not password:
                st.error("Veuillez remplir tous les champs obligatoires")
                invitation_manager.increment_attempts(token, email)
                return
            
            if not password_valid:
                st.error("Le mot de passe ne respecte pas les critères de sécurité")
                invitation_manager.increment_attempts(token, email)
                return
            
            # Import ici pour éviter import circulaire
            from database import create_pending_admin, validate_username
            
            if not validate_username(username):
                st.error("Nom d'utilisateur invalide")
                invitation_manager.increment_attempts(token, email)
                return
            
            # Créer le compte admin directement (sans validation)
            from database import hash_password_secure
            import sqlite3
            
            conn = sqlite3.connect('data/stock_kouttab.db')
            c = conn.cursor()
            
            try:
                c.execute('''
                    INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    username, 
                    hash_password_secure(password), 
                    'Super Admin', 
                    'active',
                    'Super',
                    'Admin',
                    email
                ))
                
                conn.commit()
                conn.close()
                
                # Marquer l'invitation comme utilisée
                invitation_manager.mark_invitation_used(token, email)
                
                st.success("🎉 Compte administrateur créé avec succès!")
                st.info("Vous pouvez maintenant vous connecter avec vos identifiants.")
                
                logger.info(f"Compte admin créé pour {username} ({email})")
                
                # Redirection après 3 secondes
                st.markdown("""
                <meta http-equiv="refresh" content="3;url=/" />
                <p>Redirection vers la page de connexion dans 3 secondes...</p>
                """, unsafe_allow_html=True)
                
            except sqlite3.IntegrityError as e:
                conn.close()
                st.error("Ce nom d'utilisateur existe déjà")
                invitation_manager.increment_attempts(token, email)
