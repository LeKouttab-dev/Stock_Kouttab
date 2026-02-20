import streamlit as st
import os
from datetime import datetime
from database import init_db, get_user, create_pending_admin, verify_password_secure, get_pending_admins, get_pending_stock_modifications
from ui_stock import display_stock_management
from ui_expenses import display_expense_management
from ui_admin import display_admin_page
from ui_invoices import display_invoice_deposit_page
from ui_dashboard import display_dashboard_page
from logger_config import logger
from security_middleware import security
from database_backup import display_database_export_import_page
import re
import sys

# --- Configuration pour la production sur stock.lekouttab.fr ---
# Configuration de la page pour la production
st.set_page_config(
    page_title="Gestion Stock Kouttab",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration de sécurité pour la production
if os.environ.get('ENVIRONMENT') == 'production':
    # Forcer le mode production
    try:
        st.runtime.legacy_caching.clear_cache()
    except AttributeError:
        # Alternative pour versions plus anciennes de Streamlit
        st.cache_data.clear()
        st.cache_resource.clear()
    
    # Configuration de la base de données pour la production
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/home/sc9bewu6999/stock.lekouttab.fr/data/stock_kouttab.db')
    
    # Créer le répertoire data si nécessaire
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
else:
    # Configuration pour le développement local
    DATABASE_PATH = 'data/stock_kouttab.db'

# --- Fonction de validation de mot de passe ---
def validate_password_strength(password):
    """
    Valide la force du mot de passe selon les critères de sécurité.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères"
    
    if not re.search(r'[A-Z]', password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    
    if not re.search(r'[0-9]', password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*(),.?\":{}|<>)"
    
    return True, ""

def get_password_strength_indicator(password):
    """
    Retourne un indicateur de force du mot de passe.
    """
    strength = 0
    requirements = []
    
    if len(password) >= 6:
        strength += 1
        requirements.append("✅ 6+ caractères")
    else:
        requirements.append("❌ 6+ caractères")
    
    if re.search(r'[A-Z]', password):
        strength += 1
        requirements.append("✅ Majuscule")
    else:
        requirements.append("❌ Majuscule")
    
    if re.search(r'[0-9]', password):
        strength += 1
        requirements.append("✅ Chiffre")
    else:
        requirements.append("❌ Chiffre")
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        strength += 1
        requirements.append("✅ Caractère spécial")
    else:
        requirements.append("❌ Caractère spécial")
    
    return strength, requirements
from security import validate_email, validate_username, sanitize_input
from admin_setup import check_admin_setup_mode, display_admin_setup_page
import init_admin

# --- Initialisation & Configuration ---
# Initialiser la base de données seulement si nécessaire
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True
    logger.info("Base de données initialisée.")

st.set_page_config(layout="wide", page_title="Gestion Le Kouttâb")

# Vérifier si on est en mode setup admin
if check_admin_setup_mode():
    display_admin_setup_page()
    st.stop()

st.title("📦 Gestion Le Kouttâb")

ROLES = ['Benevole', 'AdminBenevoles', 'Compta']

# --- Gestion de la session utilisateur ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# Vérifier le timeout de session si utilisateur connecté
if st.session_state.user_role is not None:
    security.check_session_timeout()

# --- Vérifier les paramètres de l'URL ---
query_params = st.query_params

# Gestion de l'invitation admin (setup_admin=true)
if "setup_admin" in query_params and query_params["setup_admin"] == "true":
    from init_admin import setup_admin_from_token
    setup_admin_from_token()
    st.stop()

# --- Vérifier les paramètres de l'URL pour le nom du produit scanné ---
if "product_name" in query_params:
    product_name = query_params["product_name"]
    st.session_state.scanned_product_name = product_name
    logger.info(f"Produit '{product_name}' reçu depuis le scanner externe.")
    st.query_params.clear()
    st.rerun()

# --- Page de Connexion / Inscription ---
if st.session_state.user_role is None:
    st.header("Accès à l'application")
    login_tab, signup_tab = st.tabs(["Se connecter", "Créer un compte"])
    
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter")
            if submitted:
                # Validation des entrées
                if not validate_username(username):
                    st.error("Nom d'utilisateur invalide")
                    security.log_security_event("LOGIN_FAILED_INVALID_USERNAME", f"Invalid username format: {username}")
                    st.stop()
                
                # Vérification tentative de connexion
                if not security.check_login_attempts(username):
                    st.stop()
                
                # Sanitization
                username = sanitize_input(username)
                
                user_data = get_user(username)
                if user_data and verify_password_secure(user_data[1], password):
                    if user_data[3] == 'active':
                        st.session_state.user_id = user_data[0]
                        st.session_state.user_role = user_data[2]
                        st.session_state.username = username
                        st.session_state.login_time = datetime.now().timestamp()
                        
                        # Réinitialiser les tentatives échouées
                        security.reset_login_attempts(username)
                        
                        logger.info(f"Connexion réussie pour l'utilisateur '{username}' avec le rôle '{user_data[2]}'.")
                        security.log_security_event("LOGIN_SUCCESS", f"User {username} logged in", username)
                        st.rerun()
                    else:
                        logger.warning(f"Tentative de connexion pour le compte en attente '{username}'.")
                        security.log_security_event("LOGIN_FAILED_PENDING", f"Pending account: {username}", username)
                        st.warning("Votre compte est en attente de validation.")
                else:
                    security.record_failed_login(username)
                    logger.warning(f"Échec de la tentative de connexion pour l'utilisateur '{username}'.")
                    security.log_security_event("LOGIN_FAILED_INVALID_CREDENTIALS", f"Invalid credentials for {username}", username)
                    st.error("Nom d'utilisateur ou mot de passe incorrect.")

    with signup_tab:
        with st.form("signup_form"):
            st.write("Informations de connexion")
            new_username = st.text_input("Nom d'utilisateur souhaité*")
            new_password = st.text_input("Choisissez un mot de passe*", type="password", help="Minimum 6 caractères: 1 majuscule, 1 chiffre, 1 caractère spécial")
            new_password_confirm = st.text_input("Confirmez le mot de passe*", type="password")
            
            # Afficher l'indicateur de force du mot de passe si un mot de passe est saisi
            if new_password:
                strength, requirements = get_password_strength_indicator(new_password)
                
                # Afficher la barre de progression (valeur entre 0.0 et 1.0)
                strength_value = strength / 4.0  # Convertit en 0.0-1.0
                st.progress(strength_value, text=f"Force du mot de passe: {strength}/4")
                
                # Afficher les exigences
                st.write("**Exigences de sécurité:**")
                for req in requirements:
                    st.write(req)
            
            # Validation du mot de passe
            password_valid = True
            password_error = ""
            
            if new_password:
                is_valid, error_msg = validate_password_strength(new_password)
                if not is_valid:
                    password_valid = False
                    password_error = error_msg
                elif new_password_confirm and new_password != new_password_confirm:
                    password_valid = False
                    password_error = "Les mots de passe ne correspondent pas"
            
            if not password_valid and password_error:
                st.error(password_error)
            
            new_role = st.selectbox("Quel est votre rôle ?*", options=ROLES)
            st.write("Informations personnelles")
            new_nom = st.text_input("Nom de famille*")
            new_prenom = st.text_input("Prénom*")
            new_email = st.text_input("Adresse e-mail*")
            new_telephone = st.text_input("Numéro de téléphone")
            signup_submitted = st.form_submit_button("Demander la création du compte")
            
            if signup_submitted:
                if all([new_username, new_password, new_password_confirm, new_role, new_nom, new_prenom, new_email]):
                    if password_valid:
                        create_pending_admin(new_username, new_password, new_role, new_nom, new_prenom, new_email, new_telephone)
                        logger.info(f"Nouvelle demande de compte pour '{new_username}' avec le rôle '{new_role}'.")
                    else:
                        st.error("Veuillez corriger les erreurs de mot de passe avant de continuer.")
                else:
                    st.error("Veuillez remplir tous les champs obligatoires (*).")

# --- Application principale (si connecté) ---
else:
    # Barre latérale
    st.sidebar.write(f"Connecté en tant que: **{st.session_state.username}**")
    st.sidebar.write(f"Rôle: **{st.session_state.user_role}**")
    if st.sidebar.button("Se déconnecter"):
        username = st.session_state.username
        security.log_security_event("LOGOUT", f"User {username} logged out", username)
        security.logout_user()
        st.rerun()

    # Notifications pour les admins
    if st.session_state.user_role == 'Super Admin':
        pending_admins = get_pending_admins()
        if not pending_admins.empty:
            st.toast(f"🔔 Vous avez {len(pending_admins)} demande(s) de compte en attente.", icon="🧑‍⚖️")
            logger.info(f"Notification affichée au Super Admin pour {len(pending_admins)} comptes en attente.")
    
    if st.session_state.user_role in ['AdminBenevoles', 'Super Admin']:
        pending_stock_mods = get_pending_stock_modifications()
        if not pending_stock_mods.empty:
            st.toast(f"🔔 {len(pending_stock_mods)} demande(s) de modification de stock en attente.", icon="📦")
            logger.info(f"Notification affichée à '{st.session_state.username}' pour {len(pending_stock_mods)} modifications de stock en attente.")

    st.sidebar.header("Navigation")
    nav_options = ["Tableau de Bord", "Gestion du Stock", "Notes de frais", "Dépôt de Factures"]
    if st.session_state.user_role in ['AdminBenevoles', 'Compta', 'Super Admin']:
        nav_options.append("Administration")
    if st.session_state.user_role == 'Super Admin':
        nav_options.append("Export/Import BDD")
    
    page = st.sidebar.radio("Aller à", nav_options)

    # Affichage de la page sélectionnée
    if page == "Tableau de Bord":
        display_dashboard_page(st.session_state.user_id, st.session_state.user_role)
    
    elif page == "Gestion du Stock":
        display_stock_management(st.session_state.user_id, st.session_state.user_role)
    
    elif page == "Notes de frais":
        display_expense_management(st.session_state.user_id, st.session_state.user_role)

    elif page == "Dépôt de Factures":
        display_invoice_deposit_page(st.session_state.user_id)

    elif page == "Administration":
        display_admin_page(st.session_state.user_id, st.session_state.user_role)
    
    elif page == "Export/Import BDD":
        display_database_export_import_page()

# --- Point d'entrée WSGI pour O2Switch ---
def application(environ, start_response):
    """
    Point d'entrée WSGI pour O2Switch Passenger
    """
    # Importer les modules nécessaires
    import sys
    from io import StringIO
    
    # Configurer l'environnement
    os.environ.update(environ)
    
    # Rediriger la sortie standard
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    try:
        # Exécuter l'application Streamlit
        main()
        
        # Récupérer la sortie
        output = sys.stdout.getvalue()
        
        # Préparer la réponse HTTP
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(output)))
        ])
        
        return [output.encode('utf-8')]
        
    except Exception as e:
        # En cas d'erreur
        error_msg = f"Erreur: {str(e)}"
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(error_msg)))
        ])
        return [error_msg.encode('utf-8')]
    
    finally:
        # Restaurer la sortie standard
        sys.stdout = old_stdout

# Point d'entrée principal pour compatibilité
def main():
    """Point d'entrée principal pour O2Switch"""
    return "Application Gestion Stock Kouttab"
