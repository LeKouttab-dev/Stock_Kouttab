import streamlit as st
from database import init_db, get_user, create_pending_admin, verify_password, get_pending_admins, get_pending_stock_modifications
from ui_stock import display_stock_management
from ui_expenses import display_expense_management
from ui_admin import display_admin_page

# --- Initialisation & Configuration ---
init_db()
st.set_page_config(layout="wide", page_title="Gestion Le Kouttâb")
st.title("📦 Gestion Le Kouttâb")

ROLES = ['Benevole', 'AdminBenevoles', 'Compta', 'Super Admin']

# --- Gestion de la session utilisateur ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

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
                user_data = get_user(username)
                if user_data and verify_password(user_data[1], password):
                    if user_data[3] == 'active':
                        st.session_state.user_id = user_data[0]
                        st.session_state.user_role = user_data[2]
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.warning("Votre compte est en attente de validation.")
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect.")

    with signup_tab:
        with st.form("signup_form"):
            st.write("Informations de connexion")
            new_username = st.text_input("Nom d'utilisateur souhaité*")
            new_password = st.text_input("Choisissez un mot de passe*", type="password")
            new_role = st.selectbox("Quel est votre rôle ?*", options=ROLES)
            st.write("Informations personnelles")
            new_nom = st.text_input("Nom de famille*")
            new_prenom = st.text_input("Prénom*")
            new_email = st.text_input("Adresse e-mail*")
            new_telephone = st.text_input("Numéro de téléphone")
            signup_submitted = st.form_submit_button("Demander la création du compte")
            if signup_submitted:
                if all([new_username, new_password, new_role, new_nom, new_prenom, new_email]):
                    create_pending_admin(new_username, new_password, new_role, new_nom, new_prenom, new_email, new_telephone)
                else:
                    st.error("Veuillez remplir tous les champs obligatoires (*).")

# --- Application principale (si connecté) ---
else:
    # Barre latérale
    st.sidebar.write(f"Connecté en tant que: **{st.session_state.username}**")
    st.sidebar.write(f"Rôle: **{st.session_state.user_role}**")
    if st.sidebar.button("Se déconnecter"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Notifications pour les admins
    if st.session_state.user_role == 'Super Admin':
        pending_admins = get_pending_admins()
        if not pending_admins.empty:
            st.toast(f"🔔 Vous avez {len(pending_admins)} demande(s) de compte en attente.", icon="🧑‍⚖️")
    
    if st.session_state.user_role in ['AdminBenevoles', 'Super Admin']:
        pending_stock_mods = get_pending_stock_modifications()
        if not pending_stock_mods.empty:
            st.toast(f"🔔 {len(pending_stock_mods)} demande(s) de modification de stock en attente.", icon="📦")


    st.sidebar.header("Navigation")
    nav_options = ["Gestion du Stock", "Notes de frais"]
    if st.session_state.user_role in ['AdminBenevoles', 'Compta', 'Super Admin']:
        nav_options.append("Administration")
    
    page = st.sidebar.radio("Aller à", nav_options)

    # Affichage de la page sélectionnée
    if page == "Gestion du Stock":
        display_stock_management(st.session_state.user_id, st.session_state.user_role)
    
    elif page == "Notes de frais":
        display_expense_management(st.session_state.user_id, st.session_state.user_role)

    elif page == "Administration":
        display_admin_page(st.session_state.user_id, st.session_state.user_role)
