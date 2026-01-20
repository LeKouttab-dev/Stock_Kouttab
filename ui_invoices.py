import streamlit as st
import pandas as pd
import os
from datetime import datetime
from email_utils import send_invoice_email
from database import get_compta_emails, get_user_profile, get_all_invoices, get_invoice_files, add_invoice, update_invoice_status
from logger_config import logger

def display_invoice_deposit_page(user_id):
    st.header("🧾 Dépôt de Factures")
    
    # Onglets pour Dépôt et Visionnage
    tab1, tab2 = st.tabs(["📤 Déposer des factures", "👁️ Visionner les factures"])
    
    with tab1:
        display_invoice_deposit_form(user_id)
    
    with tab2:
        display_invoice_viewer()

def display_invoice_deposit_form(user_id):
    st.info(
        """
        **Important :** Veuillez vous assurer que la facture est bien établie au nom de **Le Kouttâb** ou **E.C.L.A.T**.
        Les factures établies à un autre nom ne pourront pas être traitées.
        """
    )

    with st.form("invoice_form", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "Téléversez une ou plusieurs factures (PDF, PNG, JPG)",
            type=['pdf', 'png', 'jpg', 'jpeg'],
            accept_multiple_files=True
        )
        
        comment = st.text_area("Commentaire (facultatif)", placeholder="Ex: Facture d'électricité pour le mois de Juin...")
        
        submitted = st.form_submit_button("Déposer la/les facture(s)")
        
        if submitted:
            if uploaded_files:
                with st.spinner("Envoi des factures en cours..."):
                    # Récupérer le profil de l'utilisateur pour obtenir son nom complet
                    user_profile = get_user_profile(user_id)
                    user_full_name = f"{user_profile[1]} {user_profile[0]}".strip() if user_profile else "Utilisateur Inconnu"
                    
                    # Ajouter la facture à la base de données
                    facture_id = add_invoice(user_id, user_full_name, comment, uploaded_files)
                    
                    if facture_id:
                        # Envoyer l'email aux comptables
                        recipient_emails = get_compta_emails()
                        if recipient_emails:
                            send_invoice_email(
                                user_name=user_full_name,
                                comment=comment,
                                files=uploaded_files,
                                recipient_emails=recipient_emails
                            )
                            st.success("Facture(s) envoyée(s) avec succès au service comptabilité !")
                            logger.info(f"'{user_full_name}' (ID: {user_id}) a déposé {len(uploaded_files)} facture(s) (ID: {facture_id}).")
                        else:
                            st.warning("Facture(s) enregistrée(s) mais aucun destinataire (Compta/Super Admin) trouvé pour l'envoi par email.")
                    else:
                        st.error("Erreur lors de l'enregistrement des factures.")
            else:
                st.warning("Veuillez téléverser au moins une facture.")

def display_invoice_viewer():
    st.subheader("📋 Liste des factures déposées")
    
    # Récupérer toutes les factures
    invoices_df = get_all_invoices()
    
    if invoices_df.empty:
        st.info("Aucune facture déposée pour le moment.")
        return
    
    # Filtres
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        status_filter = st.selectbox(
            "Filtrer par statut:",
            options=["Toutes", "En attente", "En cours de traitement", "Validée", "Refusée"],
            key="invoice_status_filter"
        )
    
    with col2:
        date_filter = st.date_input(
            "Filtrer par date de dépôt:",
            value=None,
            key="invoice_date_filter"
        )
    
    with col3:
        search_term = st.text_input(
            "Rechercher par nom de fichier:",
            placeholder="Entrez un terme de recherche...",
            key="invoice_search"
        )
    
    # Appliquer les filtres
    filtered_df = invoices_df.copy()
    
    if status_filter != "Toutes":
        filtered_df = filtered_df[filtered_df['statut'] == status_filter]
    
    if date_filter:
        filtered_df['date_depot'] = pd.to_datetime(filtered_df['date_depot'])
        filtered_df = filtered_df[filtered_df['date_depot'].dt.date() == date_filter]
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['nom_fichier'].str.contains(search_term, case=False, na=False) |
            filtered_df['commentaire'].str.contains(search_term, case=False, na=False)
        ]
    
    # Afficher les statistiques
    st.write("### 📊 Statistiques")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total factures", len(invoices_df))
    with col2:
        st.metric("En attente", len(invoices_df[invoices_df['statut'] == 'En attente']))
    with col3:
        st.metric("En cours", len(invoices_df[invoices_df['statut'] == 'En cours de traitement']))
    with col4:
        st.metric("Validées", len(invoices_df[invoices_df['statut'] == 'Validée']))
    
    st.write("---")
    
    # Afficher les factures
    for index, row in filtered_df.iterrows():
        with st.expander(f"📄 Facture #{row['id']} - {row['fichiers_noms']} ({row['date_depot']})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Informations de la facture
                st.write(f"**Déposée par:** {row['prenom']} {row['nom']}")
                st.write(f"**Date de dépôt:** {row['date_depot']}")
                st.write(f"**Nombre de fichiers:** {row['nombre_fichiers']}")
                
                if row['commentaire']:
                    st.write(f"**Commentaire:** {row['commentaire']}")
                
                # Statut avec couleur
                status_color = {
                    'En attente': '🟡',
                    'En cours de traitement': '🔵',
                    'Validée': '🟢',
                    'Refusée': '🔴'
                }
                st.write(f"**Statut:** {status_color.get(row['statut'], '⚪')} {row['statut']}")
            
            with col2:
                # Actions
                st.write("**Actions:**")
                
                # Voir les fichiers
                if st.button(f" Voir les fichiers", key=f"view_files_{row['id']}"):
                    files = get_invoice_files(row['id'])
                    if files:
                        st.write("**Fichiers associés:**")
                        for file_name, file_path in files:
                            col_file, col_download = st.columns([3, 1])
                            with col_file:
                                st.write(f" {file_name}")
                            with col_download:
                                if os.path.exists(file_path):
                                    with open(file_path, "rb") as f:
                                        st.download_button(
                                            label="Download",
                                            data=f.read(),
                                            file_name=file_name,
                                            key=f"download_{row['id']}_{file_name}"
                                        )
                                else:
                                    st.error("Fichier non trouvé")
                
                # Mettre à jour le statut (pour les admins/compta)
                if st.session_state.user_role in ['Compta', 'Super Admin']:
                    new_status = st.selectbox(
                        "Changer le statut:",
                        options=["En attente", "En cours de traitement", "Validée", "Refusée"],
                        index=["En attente", "En cours de traitement", "Validée", "Refusée"].index(row['statut']),
                        key=f"status_{row['id']}"
                    )
                    
                    if st.button(f" Mettre à jour", key=f"update_status_{row['id']}"):
                        if update_invoice_status(row['id'], new_status):
                            st.success(f"Statut mis à jour vers: {new_status}")
                            st.rerun()
                        else:
                            st.error("Erreur lors de la mise à jour du statut")
    
    if filtered_df.empty:
        st.info("Aucune facture ne correspond aux filtres appliqués.")
