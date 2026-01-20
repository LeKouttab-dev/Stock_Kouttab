import streamlit as st
import pandas as pd
from database import (get_user_profile, update_user_profile, add_expense, 
                      get_expenses_by_user, get_all_expenses, get_files_for_expense,
                      update_expense_details, update_expense_by_accountant, delete_expense)
import os
from datetime import datetime
from logger_config import logger

UPLOADS_DIR = 'uploads'
STATUTS_REMBOURSEMENT = ['En attente', 'Approuvée', 'Refusée', 'Remboursée']

def display_expense_management(user_id, user_role):
    st.header("📝 Notes de frais")

    if user_role in ['Compta', 'Super Admin']:
        st.subheader("Dashboard de validation des notes de frais")
        all_expenses = get_all_expenses()
        if all_expenses.empty:
            st.info("Aucune note de frais à traiter pour le moment.")
        else:
            for index, row in all_expenses.iterrows():
                total = row['montant'] - row['remboursement_deja_emis'] - row['remise']
                with st.expander(f"{row['date_depense']} - {row['prenom']} {row['nom']} - TOTAL: {total:.2f}€ - Status: {row['status']}"):
                    st.write(f"**Rattachement:** {row['rattachement']}")
                    st.write(f"**Fournisseur:** {row['fournisseur']}")
                    st.write(f"**Nature de la charge:** {row['nature_charge']}")
                    st.write(f"**Commentaires de l'utilisateur:** {row['commentaires']}")
                    st.markdown("---")
                    st.write(f"**Montant brut:** {row['montant']:.2f}€")
                    st.write(f"**Remboursement déjà émis:** -{row['remboursement_deja_emis']:.2f}€")
                    st.write(f"**Remise:** -{row['remise']:.2f}€")
                    st.write(f"**TOTAL À REMBOURSER:** **{total:.2f}€**")
                    st.markdown("---")
                    
                    # Affichage du RIB
                    if row['rib']:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.text_input("IBAN (RIB) de l'utilisateur", value=row['rib'], disabled=True, key=f"rib_{row['id']}")
                        with col2:
                            if st.button("Copier le RIB", key=f"copy_rib_{row['id']}"):
                                st.write(f'<script>navigator.clipboard.writeText("{row["rib"]}")</script>', unsafe_allow_html=True)
                                st.toast("RIB copié dans le presse-papiers !")
                    else:
                        st.warning("L'utilisateur n'a pas encore renseigné son RIB.")
                    
                    st.markdown("---")

                    files = get_files_for_expense(row['id'])
                    if files:
                        for file_name in files:
                            file_path = os.path.join(UPLOADS_DIR, file_name)
                            if os.path.exists(file_path):
                                with open(file_path, "rb") as file:
                                    st.download_button(f"Télécharger {file_name}", file, file_name)
                    else:
                        st.warning("Aucun ticket fourni.")

                    with st.form(f"compta_form_{row['id']}"):
                        new_comment = st.text_area("Commentaire (visible par l'utilisateur)", value=row['commentaires_compta'] if row['commentaires_compta'] else "")
                        current_status_index = STATUTS_REMBOURSEMENT.index(row['status'])
                        new_status = st.selectbox("Changer le statut", STATUTS_REMBOURSEMENT, index=current_status_index)

                        submitted = st.form_submit_button("Mettre à jour")
                        if submitted:
                            update_expense_by_accountant(row['id'], new_status, new_comment)
                            st.toast("Note de frais mise à jour.")
                            st.rerun()
                    
                    if row['status'] == 'Remboursée':
                        with st.expander("🗑️ Zone de suppression"):
                            st.warning("Attention, cette action est irréversible et supprimera la note et tous les tickets associés.")
                            if st.button("Supprimer définitivement cette note", key=f"delete_{row['id']}"):
                                delete_expense(row['id'])
                                st.toast("Note de frais supprimée.")
                                st.rerun()
    else:
        tab1, tab2, tab3 = st.tabs(["Soumettre une note de frais", "Mes demandes", "Mon Profil (RIB)"])

        with tab1:
            st.subheader("Nouvelle note de frais")
            with st.form("expense_form", clear_on_submit=True):
                date_depense = st.date_input("Date*")
                rattachement = st.text_input("Rattachement (évènement, activité..)*")
                montant = st.number_input("Montant (€)*", min_value=0.0, format="%.2f", value=None, placeholder="0.00")
                fournisseur = st.text_input("Fournisseur")
                nature_charge = st.text_input("Nature de la charge")
                commentaires = st.text_area("Commentaires (Nombre de repas, …)")
                st.markdown("---")
                remb_emis = st.number_input("Remboursement déjà émis (espèce)", min_value=0.0, format="%.2f")
                remise = st.number_input("Remise (à préciser)", min_value=0.0, format="%.2f")
                st.markdown("---")
                uploaded_files = st.file_uploader("Ticket(s) de caisse (PNG, JPG)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
                
                submitted = st.form_submit_button("Soumettre la demande")
                if submitted:
                    if montant and date_depense and rattachement:
                        user_profile = get_user_profile(user_id)
                        user_full_name = f"{user_profile[1]} {user_profile[0]}".strip()
                        add_expense(user_id, user_full_name, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise, uploaded_files)
                        st.success("Votre note de frais a été soumise avec succès ! Les responsables ont été notifiés.")
                    else:
                        st.error("Veuillez remplir tous les champs obligatoires (*).")

        with tab2:
            st.subheader("Historique de mes demandes")
            user_expenses = get_expenses_by_user(user_id)
            if user_expenses.empty:
                st.info("Vous n'avez encore soumis aucune note de frais.")
            else:
                for index, row in user_expenses.iterrows():
                    with st.container(border=True):
                        total = row['montant'] - row['remboursement_deja_emis'] - row['remise']
                        st.write(f"**Date:** {row['date_depense']} | **Montant:** {row['montant']:.2f}€ | **Total demandé:** {total:.2f}€ | **Statut:** {row['status']}")
                        st.write(f"_{row['rattachement']}_")

                        if row['commentaires_compta']:
                            st.info(f"💬 Commentaire de la comptabilité : {row['commentaires_compta']}")

                        if row['status'] == 'En attente':
                            with st.expander("✏️ Éditer la note de frais"):
                                with st.form(f"edit_form_{row['id']}"):
                                    st.write("Pour modifier les tickets, veuillez supprimer cette note et la recréer.")
                                    
                                    edit_date = st.date_input("Date*", value=datetime.strptime(row['date_depense'], '%Y-%m-%d').date(), key=f"date_{row['id']}")
                                    edit_rattachement = st.text_input("Rattachement*", value=row['rattachement'], key=f"ratt_{row['id']}")
                                    edit_montant = st.number_input("Montant (€)*", value=row['montant'], min_value=0.01, format="%.2f", key=f"montant_{row['id']}")
                                    edit_fournisseur = st.text_input("Fournisseur", value=row['fournisseur'], key=f"fourn_{row['id']}")
                                    edit_nature = st.text_input("Nature de la charge", value=row['nature_charge'], key=f"nature_{row['id']}")
                                    edit_commentaires = st.text_area("Commentaires", value=row['commentaires'], key=f"comm_{row['id']}")
                                    edit_remb_emis = st.number_input("Remboursement déjà émis", value=row['remboursement_deja_emis'], min_value=0.0, format="%.2f", key=f"remb_{row['id']}")
                                    edit_remise = st.number_input("Remise", value=row['remise'], min_value=0.0, format="%.2f", key=f"remise_{row['id']}")

                                    update_submitted = st.form_submit_button("Mettre à jour la note")
                                    if update_submitted:
                                        if edit_rattachement and edit_montant:
                                            update_expense_details(row['id'], edit_date, edit_rattachement, edit_fournisseur, edit_nature, edit_montant, edit_commentaires, edit_remb_emis, edit_remise)
                                            st.success("Note de frais mise à jour avec succès !")
                                            st.rerun()
                                        else:
                                            st.error("Le rattachement et le montant sont obligatoires.")

        with tab3:
            st.subheader("Mes informations de remboursement")
            profile_data = get_user_profile(user_id)
            with st.form("profile_form"):
                nom, prenom, email, telephone, rib = profile_data
                new_nom = st.text_input("Nom", value=nom)
                new_prenom = st.text_input("Prénom", value=prenom)
                new_email = st.text_input("Email", value=email)
                new_telephone = st.text_input("Téléphone", value=telephone)
                new_rib = st.text_input("IBAN (RIB)", value=rib if rib else "")
                profile_submitted = st.form_submit_button("Mettre à jour mon profil")
                if profile_submitted:
                    update_user_profile(user_id, new_nom, new_prenom, new_email, new_telephone, new_rib)
                    st.success("Votre profil a été mis à jour.")
