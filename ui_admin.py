import streamlit as st
import pandas as pd
from database import (get_pending_admins, update_validation_status, delete_admin, 
                      get_all_users, update_user_role, get_all_items, add_item, 
                      update_item_details, delete_item, get_pending_stock_modifications,
                      approve_stock_modification, refuse_stock_modification,
                      get_categories_with_subcategories, add_subcategory, import_inventory_from_csv,
                      get_all_categories, get_all_subcategories, update_category, delete_category,
                      update_subcategory, delete_subcategory, add_category)
import emoji
from logger_config import logger
from csv_import import display_csv_import

def get_emoji_list():
    emoji_list = []
    for e in emoji.EMOJI_DATA:
        french_alias = emoji.demojize(e, language='fr')
        clean_alias = french_alias.replace('_', ' ').strip(':')
        emoji_list.append(f"{e} {clean_alias}")
    return sorted(emoji_list)

EMOJI_LIST = get_emoji_list()
ROLES = ['Benevole', 'AdminBenevoles', 'Compta', 'Super Admin']
MAIN_CATEGORIES = ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"]

@st.dialog("Article Ajouté")
def item_added_dialog(item_name):
    st.success(f"L'article **{item_name}** a été ajouté avec succès !")
    if st.button("OK"):
        st.rerun()

@st.dialog("Nouvelle Sous-catégorie")
def add_subcategory_dialog(category_name):
    st.write(f"Ajouter une nouvelle sous-catégorie à **{category_name}**")
    new_subcat = st.text_input("Nom de la nouvelle sous-catégorie")
    if st.button("Ajouter"):
        if new_subcat:
            if add_subcategory(category_name, new_subcat):
                st.session_state.newly_added_subcategory = new_subcat
                st.rerun()
            else:
                st.warning("Cette sous-catégorie existe déjà.")
        else:
            st.error("Le nom ne peut pas être vide.")

def display_admin_page(user_id, user_role):
    st.header("Panneau d'Administration")

    CATEGORIES = get_categories_with_subcategories()

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
                            logger.info(f"Rôle de '{user['username']}' mis à jour vers '{new_role}' par '{st.session_state.username}'.")
                            st.toast(f"Rôle de {user['username']} mis à jour.")
                            st.rerun()
                    with c2:
                        if st.button("🗑️", key=f"delete_user_{user['id']}", help=f"Supprimer {user['username']}"):
                            delete_admin(user['id'])
                            logger.warning(f"Utilisateur '{user['username']}' supprimé par '{st.session_state.username}'.")
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
                            approve_stock_modification(mod['id'], mod['id_stock'], mod['quantite_demandee'], st.session_state.user_id)
                            logger.info(f"Modification de stock pour '{mod['stock_nom']}' approuvée par '{st.session_state.username}'.")
                            st.toast("Modification approuvée !")
                            st.rerun()
                    with c2:
                        if st.button("Refuser", key=f"refuse_stock_{mod['id']}", use_container_width=True):
                            refuse_stock_modification(mod['id'])
                            logger.warning(f"Modification de stock pour '{mod['stock_nom']}' refusée par '{st.session_state.username}'.")
                            st.toast("Modification refusée.")
                            st.rerun()
        else:
            st.info("Aucune demande de modification de stock en attente.")
        st.markdown("---")

        st.subheader("Gestion des articles du stock")
        
        # Onglets pour Ajout manuel, Importation CSV et Gestion des catégories
        tab1, tab2, tab3 = st.tabs(["➕ Ajout manuel", "📁 Importation CSV", "🏷️ Gérer catégories"])
        
        with tab1:
            display_manual_item_form(CATEGORIES)
        
        with tab2:
            display_csv_import()
        
        with tab3:
            display_category_management()

        st.markdown("---")
        st.subheader("Gérer les articles existants")
        items_to_manage = get_all_items()
        if not items_to_manage.empty:
            for index, row in items_to_manage.iterrows():
                with st.expander(f"{row.get('emoji', '📦')} Modifier/Supprimer : **{row['nom']}**"):
                    edit_nom = st.text_input("Nom", value=row['nom'], key=f"edit_nom_{row['id']}")
                    edit_emoji = st.selectbox("Emoji", options=EMOJI_LIST, 
                                  index=EMOJI_LIST.index(next((e for e in EMOJI_LIST if e.startswith(row['emoji'])), EMOJI_LIST[0])) if pd.notna(row.get('emoji')) else 0, 
                                  key=f"edit_emoji_{row['id']}")
                    
                    edit_categorie = st.selectbox("Catégorie", options=MAIN_CATEGORIES, 
                                    index=MAIN_CATEGORIES.index(row['categorie']) if pd.notna(row['categorie']) and row['categorie'] in MAIN_CATEGORIES else 0, 
                                    key=f"edit_cat_{row['id']}")
                    
                    edit_sous_categorie = None
                    if edit_categorie == "Nourriture":
                        sc_options = CATEGORIES.get(edit_categorie, [])
                        current_sc_index = sc_options.index(row['sous_categorie']) if pd.notna(row['sous_categorie']) and row['sous_categorie'] in sc_options else 0
                        edit_sous_categorie = st.selectbox(f"Sous-catégorie pour {edit_categorie}", options=sc_options, index=current_sc_index, key=f"edit_sc_{row['id']}")

                    edit_quantite = st.number_input("Quantité", min_value=0, value=row['quantite'], key=f"edit_qty_{row['id']}")
                    edit_seuil_alerte = st.number_input("Seuil d'alerte", min_value=0, value=row['seuil_alerte'], key=f"edit_seuil_{row['id']}")
                    
                    col_update, col_delete = st.columns(2)
                    with col_update:
                        if st.button("Mettre à jour", key=f"update_{row['id']}"):
                            if update_item_details(row['id'], edit_nom, edit_categorie, edit_sous_categorie, edit_quantite, edit_seuil_alerte, edit_emoji):
                                st.success(f"Article '{edit_nom}' mis à jour."); st.rerun()
                    with col_delete:
                        if st.button("Supprimer", key=f"delete_{row['id']}"):
                            delete_item(row['id']); st.success(f"Article '{row['nom']}' supprimé."); st.rerun()
        else:
            st.info("Aucun article à gérer.")
    elif user_role not in ['Super Admin']:
         st.info("Cette section est réservée aux administrateurs du stock et au Super Admin.")

def display_manual_item_form(CATEGORIES):
    st.write("#### Ajouter un article")
    
    # Bouton pour ajouter une sous-catégorie, en dehors du formulaire principal
    st.write("Gérer les sous-catégories de nourriture :")
    if st.button("➕ Ajouter une sous-catégorie à Nourriture"):
        add_subcategory_dialog("Nourriture")

    with st.form("add_item_form"):
        new_nom = st.text_input("Nom de l'article")
        new_emoji = st.selectbox("Emoji", options=EMOJI_LIST, index=None, placeholder="Sélectionnez un emoji...")
        
        new_categorie = st.selectbox("Catégorie", options=MAIN_CATEGORIES)
        
        new_sous_categorie = None
        if new_categorie == "Nourriture":
            subcat_options = CATEGORIES.get(new_categorie, [])
            newly_added = st.session_state.get("newly_added_subcategory")
            index = subcat_options.index(newly_added) if newly_added and newly_added in subcat_options else 0
            new_sous_categorie = st.selectbox(f"Sous-catégorie pour {new_categorie}", options=subcat_options, index=index)

        new_quantite = st.number_input("Quantité initiale", min_value=0, value=0)
        new_seuil_alerte = st.number_input("Seuil d'alerte", min_value=0, value=5)
        
        add_submitted = st.form_submit_button("Ajouter l'article")
        if add_submitted:
            if new_nom and new_emoji:
                if add_item(new_nom, new_categorie, new_sous_categorie, new_quantite, new_seuil_alerte, new_emoji):
                    st.session_state.item_to_add = new_nom
                    if "newly_added_subcategory" in st.session_state:
                        del st.session_state.newly_added_subcategory
            else:
                st.error("Le nom de l'article et l'emoji sont obligatoires.")
    
    if 'item_to_add' in st.session_state and st.session_state.item_to_add:
        item_added_dialog(st.session_state.item_to_add)
        st.session_state.item_to_add = None

def display_category_management():
    st.write("#### Gestion des catégories et sous-catégories")
    
    # Onglets pour Catégories et Sous-catégories
    cat_tab, subcat_tab = st.tabs(["📂 Catégories", "🏷️ Sous-catégories"])
    
    with cat_tab:
        display_categories_management()
    
    with subcat_tab:
        display_subcategories_management()

def display_categories_management():
    st.write("**Gestion des catégories principales**")
    
    # Ajouter une nouvelle catégorie
    with st.expander("➕ Ajouter une nouvelle catégorie", expanded=False):
        new_category = st.text_input("Nom de la nouvelle catégorie", key="new_category_name")
        if st.button("Ajouter la catégorie", key="add_category_btn"):
            if new_category.strip():
                success, message = add_category(new_category.strip())
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Veuillez entrer un nom de catégorie valide")
    
    # Afficher et gérer les catégories existantes
    categories = get_all_categories()
    
    if not categories:
        st.info("Aucune catégorie trouvée.")
        return
    
    st.write(f"**{len(categories)} catégorie(s) trouvée(s)**")
    
    for category in categories:
        with st.expander(f"📂 {category}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                edit_name = st.text_input("Nouveau nom", value=category, key=f"edit_cat_{category}")
            
            with col2:
                if st.button("✏️ Modifier", key=f"update_cat_{category}"):
                    if edit_name.strip() and edit_name != category:
                        success = update_category(category, edit_name.strip())
                        if success:
                            st.success(f"Catégorie renommée en '{edit_name}'")
                            st.rerun()
                        else:
                            st.error("Erreur lors de la modification")
                    elif edit_name == category:
                        st.warning("Aucun changement détecté")
                    else:
                        st.error("Veuillez entrer un nom valide")
            
            with col3:
                if st.button("🗑️ Supprimer", key=f"delete_cat_{category}"):
                    success, message = delete_category(category)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

def display_subcategories_management():
    st.write("**Gestion des sous-catégories**")
    
    # Ajouter une nouvelle sous-catégorie
    with st.expander("➕ Ajouter une nouvelle sous-catégorie", expanded=False):
        all_categories = get_all_categories()
        if not all_categories:
            st.warning("Aucune catégorie disponible. Veuillez d'abord créer des catégories.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_category = st.selectbox("Catégorie parente", options=all_categories, key="new_subcat_cat")
            with col2:
                new_subcategory = st.text_input("Nom de la sous-catégorie", key="new_subcat_name")
            
            if st.button("Ajouter la sous-catégorie", key="add_subcat_btn"):
                if new_subcategory.strip():
                    success = add_subcategory(selected_category, new_subcategory.strip())
                    if success:
                        st.success(f"Sous-catégorie '{new_subcategory}' ajoutée à '{selected_category}'")
                        st.rerun()
                    else:
                        st.error("Erreur lors de l'ajout")
                else:
                    st.error("Veuillez entrer un nom de sous-catégorie valide")
    
    # Afficher et gérer les sous-catégories existantes
    subcategories = get_all_subcategories()
    
    if not subcategories:
        st.info("Aucune sous-catégorie trouvée.")
        return
    
    st.write(f"**{len(subcategories)} sous-catégorie(s) trouvée(s)**")
    
    for subcat_id, category, subcat_name in subcategories:
        with st.expander(f"🏷️ {category} > {subcat_name}"):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                all_cats = get_all_categories()
                edit_category = st.selectbox("Catégorie", options=all_cats, 
                                            index=all_cats.index(category) if category in all_cats else 0,
                                            key=f"edit_subcat_cat_{subcat_id}")
                edit_name = st.text_input("Nouveau nom", value=subcat_name, key=f"edit_subcat_name_{subcat_id}")
            
            with col2:
                if st.button("✏️ Modifier", key=f"update_subcat_{subcat_id}"):
                    if edit_name.strip():
                        success = update_subcategory(subcat_id, edit_category, edit_name.strip())
                        if success:
                            st.success("Sous-catégorie mise à jour")
                            st.rerun()
                        else:
                            st.error("Erreur lors de la modification")
                    else:
                        st.error("Veuillez entrer un nom valide")
            
            with col3:
                if st.button("🗑️ Supprimer", key=f"delete_subcat_{subcat_id}"):
                    success, message = delete_subcategory(subcat_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            
            with col4:
                # Afficher le nombre d'articles dans cette sous-catégorie
                from database import get_all_items
                items = get_all_items()
                count = len(items[(items['categorie'] == category) & (items['sous_categorie'] == subcat_name)])
                st.metric("Articles", count)
