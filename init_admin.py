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
    import sqlite3
    conn = sqlite3.connect('data/stock_kouttab.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM Admins WHERE role = 'Super Admin' AND validation_status = 'active'")
    admin_count = c.fetchone()[0]
    conn.close()
    
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
