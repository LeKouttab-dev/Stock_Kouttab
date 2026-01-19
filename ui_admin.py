import streamlit as st
import pandas as pd
from database import (get_pending_admins, update_validation_status, delete_admin, 
                      get_all_users, update_user_role, get_all_items, add_item, 
                      update_item_details, delete_item, get_pending_stock_modifications,
                      approve_stock_modification, refuse_stock_modification)
import emoji

def get_emoji_list():
    emoji_list = []
    for e in emoji.EMOJI_DATA:
        french_alias = emoji.demojize(e, language='fr')
        clean_alias = french_alias.replace('_', ' ').strip(':')
        emoji_list.append(f"{e} {clean_alias}")
    return sorted(emoji_list)

EMOJI_LIST = get_emoji_list()
ROLES = ['Benevole', 'AdminBenevoles', 'Compta', 'Super Admin']

@st.dialog("Article Ajouté")
def item_added_dialog(item_name):
    st.success(f"L'article **{item_name}** a été ajouté avec succès !")
    if st.button("OK"):
        st.rerun()

def display_admin_page(user_id, user_role):
    st.header("Panneau d'Administration")

    if user_role == 'Super Admin':
        st.subheader("Validation des nouveaux comptes")
        pending_admins = get_pending_admins()
        if not pending_admins.empty:
            for index, admin in pending_admins.iterrows():
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"Demande de: **{admin['username']}** (Rôle: *{admin['role']}*)")
                with col2:
                    if st.button("Approuver", key=f"approve_{admin['id']}"):
                        update_validation_status(admin['id'], 'active'); st.rerun()
                with col3:
                    if st.button("Refuser", key=f"deny_{admin['id']}"):
                        delete_admin(admin['id']); st.rerun()
        else:
            st.info("Aucune demande de compte en attente.")
        st.markdown("---")

        st.subheader("Gestion des utilisateurs existants")
        all_users = get_all_users(user_id)
        if not all_users.empty:
            for index, user in all_users.iterrows():
                with st.expander(f"{user['prenom']} {user['nom']} ({user['username']}) - Rôle: {user['role']}"):
                    current_role_index = ROLES.index(user['role'])
                    new_role = st.selectbox("Changer le rôle", options=ROLES, index=current_role_index, key=f"role_{user['id']}")
                    
                    c1, c2 = st.columns([1, 0.2])
                    with c1:
                        if st.button("Mettre à jour le rôle", key=f"update_role_{user['id']}", use_container_width=True):
                            update_user_role(user['id'], new_role)
                            st.toast(f"Rôle de {user['username']} mis à jour.")
                            st.rerun()
                    with c2:
                        if st.button("🗑️", key=f"delete_user_{user['id']}", help=f"Supprimer {user['username']}"):
                            delete_admin(user['id'])
                            st.toast(f"Utilisateur {user['username']} supprimé.")
                            st.rerun()
        else:
            st.info("Aucun autre utilisateur à gérer.")
        st.markdown("---")

    if user_role in ['AdminBenevoles', 'Super Admin']:
        st.subheader("Validation des modifications de stock")
        pending_mods = get_pending_stock_modifications()
        if not pending_mods.empty:
            for index, mod in pending_mods.iterrows():
                with st.container(border=True):
                    st.write(f"**Demandeur:** {mod['prenom']} {mod['user_nom']}")
                    st.write(f"**Article:** {mod['stock_nom']}")
                    st.write(f"**Modification demandée:** {mod['quantite_actuelle']} ➔ **{mod['quantite_demandee']}**")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Approuver", key=f"approve_stock_{mod['id']}", use_container_width=True):
                            approve_stock_modification(mod['id'], mod['id_stock'], mod['quantite_demandee'])
                            st.toast("Modification approuvée !")
                            st.rerun()
                    with c2:
                        if st.button("Refuser", key=f"refuse_stock_{mod['id']}", use_container_width=True):
                            refuse_stock_modification(mod['id'])
                            st.toast("Modification refusée.")
                            st.rerun()
        else:
            st.info("Aucune demande de modification de stock en attente.")
        st.markdown("---")

        st.subheader("Gestion des articles du stock")
        # Utiliser st.session_state pour gérer la soumission et l'affichage du dialogue
        if 'item_to_add' not in st.session_state:
            st.session_state.item_to_add = None

        with st.form("add_item_form", clear_on_submit=True):
            new_nom = st.text_input("Nom de l'article")
            new_emoji = st.selectbox("Emoji", options=EMOJI_LIST, index=None, placeholder="Sélectionnez un emoji...", help="Tapez pour rechercher")
            new_categorie = st.selectbox("Catégorie", ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"])
            new_quantite = st.number_input("Quantité initiale", min_value=0, value=0)
            new_seuil_alerte = st.number_input("Seuil d'alerte", min_value=0, value=5)
            add_submitted = st.form_submit_button("Ajouter l'article")
            if add_submitted:
                if new_nom and new_emoji:
                    if add_item(new_nom, new_categorie, new_quantite, new_seuil_alerte, new_emoji):
                        st.session_state.item_to_add = new_nom
                else:
                    st.error("Le nom de l'article et l'emoji sont obligatoires.")
        
        if st.session_state.item_to_add:
            item_added_dialog(st.session_state.item_to_add)
            st.session_state.item_to_add = None # Réinitialiser après affichage

        st.markdown("---")
        st.subheader("Gérer les articles existants")
        items_to_manage = get_all_items()
        if not items_to_manage.empty:
            for index, row in items_to_manage.iterrows():
                with st.expander(f"{row.get('emoji', '📦')} Modifier/Supprimer : **{row['nom']}**"):
                    current_emoji_char = row.get('emoji', '📦')
                    current_emoji_formatted = next((item for item in EMOJI_LIST if item.startswith(current_emoji_char)), None)
                    current_emoji_index = EMOJI_LIST.index(current_emoji_formatted) if current_emoji_formatted else 0
                    edit_nom = st.text_input("Nom", value=row['nom'], key=f"edit_nom_{row['id']}")
                    edit_emoji = st.selectbox("Emoji", options=EMOJI_LIST, index=current_emoji_index, key=f"edit_emoji_{row['id']}", help="Tapez pour rechercher")
                    edit_categorie = st.selectbox("Catégorie", ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"], index=["Nourriture", "Fournitures", "Intendance", "Bibliothèque"].index(row['categorie']), key=f"edit_cat_{row['id']}")
                    edit_quantite = st.number_input("Quantité", min_value=0, value=row['quantite'], key=f"edit_qty_{row['id']}")
                    edit_seuil_alerte = st.number_input("Seuil d'alerte", min_value=0, value=row['seuil_alerte'], key=f"edit_seuil_{row['id']}")
                    col_update, col_delete = st.columns(2)
                    with col_update:
                        if st.button("Mettre à jour", key=f"update_{row['id']}"):
                            if update_item_details(row['id'], edit_nom, edit_categorie, edit_quantite, edit_seuil_alerte, edit_emoji):
                                st.success(f"Article '{edit_nom}' mis à jour."); st.rerun()
                    with col_delete:
                        if st.button("Supprimer", key=f"delete_{row['id']}"):
                            delete_item(row['id']); st.success(f"Article '{row['nom']}' supprimé."); st.rerun()
        else:
            st.info("Aucun article à gérer.")
    elif user_role not in ['Super Admin']:
         st.info("Cette section est réservée aux administrateurs du stock et au Super Admin.")
