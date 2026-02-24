import streamlit as st
from database import init_db
from invitation_manager import invitation_manager
from admin_setup import send_admin_invitation_email, generate_invitation_url
from logger_config import logger

def generate_first_admin_invitation():
    """Page pour générer la première invitation admin"""
    st.title("🔐 Configuration Initiale - Premier Administrateur")
    
    st.markdown("""
    ### Bienvenue dans Gestion Le Kouttâb !
    
    Pour démarrer, nous devons créer le premier compte administrateur.
    Cette étape n'est nécessaire que lors de la première installation.
    """)
    
    # Vérifier si un admin existe déjà
    from database import get_db_connection, init_db
    conn = get_db_connection()
    if conn is None:
        st.error("❌ Impossible de se connecter à la base de données. Vérifiez la configuration dans st.secrets.")
        return
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM Admins WHERE role = 'Super Admin' AND validation_status = 'active'")
        admin_count = c.fetchone()[0]
    except Exception as e:
        # La table n'existe pas encore — initialiser la base puis réessayer
        try:
            init_db()
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM Admins WHERE role = 'Super Admin' AND validation_status = 'active'")
            admin_count = c.fetchone()[0]
        except Exception as e2:
            st.error(f"❌ Erreur lors de l'accès à la base de données : {e2}")
            return

    if admin_count > 0:
        st.success("✅ Un administrateur est déjà configuré!")
        st.info("Vous pouvez maintenant utiliser l'application normalement.")
        if st.button("Aller à la page de connexion"):
            st.query_params.clear()
            st.rerun()
        return
    
    with st.form("generate_invitation"):
        st.subheader("Générer l'invitation administrateur")
        
        admin_email = st.text_input(
            "Email de l'administrateur*", 
            help="L'email recevra le lien de configuration sécurisée"
        )
        
        st.markdown("---")
        st.info("📧 **Note:** Un email avec un lien sécurisé sera envoyé à cette adresse. Le lien expirera dans 24 heures.")
        
        submitted = st.form_submit_button("📤 Envoyer l'invitation", type="primary")
        
        if submitted:
            if not admin_email:
                st.error("Veuillez entrer une adresse email")
                return
            
            # Validation email
            from security import validate_email
            if not validate_email(admin_email):
                st.error("Format d'email invalide")
                return
            
            # Générer l'invitation
            token, expires_at = invitation_manager.generate_admin_invitation(admin_email)
            
            if token is None:
                st.error("Une invitation a déjà été envoyée à cet email")
                return
            
            # Générer l'URL
            invitation_url = generate_invitation_url(token, admin_email)
            
            # Envoyer l'email
            if send_admin_invitation_email(admin_email, invitation_url):
                st.success("🎉 Invitation envoyée avec succès!")
                
                st.markdown(f"""
                ### ✅ Étapes suivantes :
                
                1. **Consultez votre boîte mail** : {admin_email}
                2. **Cliquez sur le lien sécurisé** reçu
                3. **Configurez votre compte** administrateur
                
                ---
                
                🔗 **Lien d'invitation (pour test uniquement)** :
                ```
                {invitation_url}
                ```
                
                ⏰ **Expiration** : {expires_at.strftime('%d/%m/%Y à %H:%M')}
                """)
                
                logger.info(f"Première invitation admin générée pour {admin_email}")
                
            else:
                st.error("❌ Erreur lors de l'envoi de l'email")
                st.warning("Vérifiez votre configuration SMTP dans secrets.toml")
                
                # Afficher le lien quand même pour le développement
                st.markdown(f"""
                ### 🔧 Lien de secours (développement) :
                ```
                {invitation_url}
                ```
                """)

# Vérifier si on est sur la page d'initialisation
if st.query_params.get("init_admin") == "true":
    generate_first_admin_invitation()
    st.stop()

def setup_admin_from_token():
    """Gère la configuration admin depuis un lien d'invitation"""
    st.title("🔐 Configuration du Compte Administrateur")
    
    query_params = st.query_params
    token = query_params.get("token")
    email = query_params.get("email")
    
    if not token or not email:
        st.error("❌ Lien d'invitation invalide")
        return
    
    # Valider le token
    from invitation_manager import invitation_manager
    is_valid, message = invitation_manager.validate_invitation_token(token, email)
    
    if not is_valid:
        st.error(f"❌ {message}")
        st.warning("Le lien a peut-être expiré ou déjà été utilisé.")
        return
    
    # Formulaire de création du compte
    with st.form("setup_admin_form"):
        st.subheader(f"Création du compte pour {email}")
        
        username = st.text_input("Nom d'utilisateur*", help="Choisissez un nom d'utilisateur unique")
        password = st.text_input("Mot de passe*", type="password", help="Minimum 6 caractères")
        password_confirm = st.text_input("Confirmer le mot de passe*", type="password")
        
        # Validation du mot de passe
        password_valid = True
        password_error = ""
        
        if password and len(password) < 6:
            password_valid = False
            password_error = "Le mot de passe doit contenir au moins 6 caractères"
        elif password and password_confirm and password != password_confirm:
            password_valid = False
            password_error = "Les mots de passe ne correspondent pas"
        
        if not password_valid:
            st.error(password_error)
        
        submitted = st.form_submit_button("🚀 Créer le compte administrateur", type="primary")
        
        if submitted:
            if all([username, password, password_confirm]) and password_valid:
                # Créer le compte admin
                from database import create_user_direct
                success = create_user_direct(
                    username=username,
                    password=password,
                    role='Super Admin',
                    nom=email.split('@')[0],
                    prenom="Admin",
                    email=email,
                    telephone="",
                    validation_status='active'
                )
                
                if success:
                    # Marquer l'invitation comme utilisée
                    invitation_manager.mark_invitation_used(token, email)
                    
                    st.success("✅ Compte administrateur créé avec succès !")
                    st.info("Vous pouvez maintenant vous connecter.")
                    
                    # Nettoyer l'URL
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de la création du compte")
            else:
                st.error("Veuillez remplir tous les champs obligatoires")
