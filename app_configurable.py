import streamlit as st
from datetime import datetime
from database import init_db, get_user, create_pending_admin, verify_password_secure, get_pending_admins, get_pending_stock_modifications
from ui_stock import display_stock_management
from ui_expenses import display_expense_management
from ui_admin import display_admin_page
from ui_invoices import display_invoice_deposit_page
from ui_dashboard import display_dashboard_page
from logger_config import logger
from security_middleware import security
from security import validate_email, validate_username, sanitize_input
from admin_setup import check_admin_setup_mode, display_admin_setup_page
from config_manager import get_config
import init_admin

# --- Initialisation & Configuration ---
init_db()

# Charger la configuration selon l'environnement
config = get_config()
st.set_page_config(layout="wide", page_title="Gestion Le Kouttâb")

# Afficher le mode actuel
if config['debug']:
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🏠 **Mode Local**")
    st.sidebar.markdown(f"🌐 URL: {config['base_url']}")
else:
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🌐 **Mode Production**")
    st.sidebar.markdown(f"🌐 URL: {config['base_url']}")

# Vérifier si on est en mode setup admin
if check_admin_setup_mode():
    display_admin_setup_page()
    st.stop()

# Vérifier timeout de session si utilisateur connecté
if 'user_role' in st.session_state:
    if 'login_time' in st.session_state:
        login_time = st.session_state.login_time
        current_time = datetime.now().timestamp()
        
        # Timeout après 1 heure (3600 secondes)
        if current_time - login_time > 3600:
            security.logout_user()
            st.warning("⏰ Session expirée. Veuillez vous reconnecter.")
            st.rerun()

# --- Page de connexion ---
if 'user_role' not in st.session_state:
    st.title("🔐 Gestion Le Kouttâb - Connexion")
    
    login_tab, signup_tab = st.tabs(["🔑 Connexion", "👤 Créer un compte"])
    
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
            new_password = st.text_input("Choisissez un mot de passe*", type="password", help="Le mot de passe doit contenir au moins 6 caractères")
            new_password_confirm = st.text_input("Confirmez le mot de passe*", type="password")
            
            # Validation du mot de passe
            password_valid = True
            password_error = ""
            
            if new_password and len(new_password) < 6:
                password_valid = False
                password_error = "Le mot de passe doit contenir au moins 6 caractères"
            elif new_password and new_password_confirm and new_password != new_password_confirm:
                password_valid = False
                password_error = "Les mots de passe ne correspondent pas"
            
            if not password_valid:
                st.error(password_error)
            
            new_role = st.selectbox("Quel est votre rôle ?*", options=["AdminBenevoles", "Compta", "Super Admin"])
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
                        st.success("✅ Demande de compte créée avec succès ! Un administrateur va valider votre demande.")
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
