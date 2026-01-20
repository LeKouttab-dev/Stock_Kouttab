import streamlit as st
import pandas as pd
from database import get_all_items, update_quantity, create_stock_modification_request, get_categories_with_subcategories
from logger_config import logger

ICONS = {"Nourriture": "🍔", "Fournitures": "📝", "Intendance": "🧼", "Bibliothèque": "📚"}

@st.dialog("Demande de modification de stock")
def request_stock_change_dialog(user_id, item_id, item_name, current_qty):
    st.write(f"Vous demandez à modifier la quantité pour **{item_name}**.")
    st.write(f"Quantité actuelle : **{current_qty}**")
    
    if 'request_sent_in_dialog' not in st.session_state:
        st.session_state.request_sent_in_dialog = False

    if st.session_state.request_sent_in_dialog:
        st.success("✅ Votre demande a été envoyée pour validation.")
        if st.button("Fermer"):
            st.session_state.request_sent_in_dialog = False
            st.rerun()
    else:
        requested_qty = st.number_input("Nouvelle quantité souhaitée", min_value=0, value=current_qty, key="requested_qty_dialog")
        if st.button("Envoyer la demande"):
            create_stock_modification_request(user_id, item_id, current_qty, requested_qty)
            st.session_state.request_sent_in_dialog = True
            st.rerun()

@st.dialog("Modification directe du stock")
def admin_stock_change_dialog(user_id, item_id, item_name, current_qty):
    st.write(f"Modification directe pour **{item_name}**.")
    st.write(f"Quantité actuelle : **{current_qty}**")
    
    new_qty = st.number_input("Nouvelle quantité", min_value=0, value=current_qty, key="admin_qty_dialog")
    
    if st.button("Mettre à jour", type="primary"):
        if new_qty != current_qty:
            update_quantity(item_id, new_qty, user_id)
            st.success(f"✅ Quantité mise à jour : {current_qty} → {new_qty}")
            st.rerun()
        else:
            st.warning("Aucune modification détectée.")
    
    if st.button("Annuler"):
        st.rerun()

def display_stock_management(user_id, user_role):
    st.header("Tableau de Bord du Stock")

    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None
    if 'selected_subcategory' not in st.session_state:
        st.session_state.selected_subcategory = None

    df = get_all_items()
    CATEGORIES = get_categories_with_subcategories()

    # --- Vue 3: Affichage des produits ---
    if st.session_state.selected_category and st.session_state.selected_subcategory:
        if st.button(f"⬅️ Retour à {st.session_state.selected_category}"):
            st.session_state.selected_subcategory = None
            st.rerun()

        st.subheader(f"Articles pour : {st.session_state.selected_subcategory}")
        product_df = df[(df['categorie'] == st.session_state.selected_category) & (df['sous_categorie'] == st.session_state.selected_subcategory)].sort_values(by='nom')

        if product_df.empty:
            st.info(f"Aucun article dans cette sous-catégorie.")
        else:
            cols = st.columns(2)
            for i, row in product_df.iterrows():
                with cols[i % 2]:
                    with st.container(border=True):
                        st.subheader(f"{row.get('emoji', '📦')} {row['nom']}")
                        if row['quantite'] < row['seuil_alerte']:
                            st.markdown(f"⚠️ <span style='color:red;'>Seuil bas ({row['seuil_alerte']})</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"Seuil d'alerte : {row['seuil_alerte']}")
                        
                        if user_role in ['AdminBenevoles', 'Super Admin']:
                            st.metric(label="Quantité en stock", value=row['quantite'])
                            if st.button(" Modifier", key=f"edit_{row['id']}", use_container_width=True):
                                admin_stock_change_dialog(user_id, row['id'], row['nom'], row['quantite'])
                        else:
                            st.metric(label="Quantité en stock", value=row['quantite'])
                            if st.button("Demander une modification", key=f"request_{row['id']}"):
                                request_stock_change_dialog(user_id, row['id'], row['nom'], row['quantite'])

    # --- Vue 2: Affichage des sous-catégories (pour Nourriture) ou des produits (autres) ---
    elif st.session_state.selected_category:
        category = st.session_state.selected_category
        
        if st.button("⬅️ Retour aux catégories principales"):
            st.session_state.selected_category = None
            st.rerun()

        # Si la catégorie est "Nourriture", on montre les sous-catégories
        if category == "Nourriture":
            st.subheader(f"Sous-catégories pour {category}")
            subcategories = CATEGORIES.get(category, [])
            
            if not subcategories:
                st.warning("Aucune sous-catégorie définie pour la nourriture.")
            else:
                col1, col2 = st.columns(2)
                grid_cols = [col1, col2] * ((len(subcategories) + 1) // 2)

                for i, subcat in enumerate(subcategories):
                    with grid_cols[i]:
                        with st.container(border=True):
                            subcat_df = df[df['sous_categorie'] == subcat]
                            num_items = len(subcat_df)
                            alerts = subcat_df[subcat_df['quantite'] < subcat_df['seuil_alerte']]
                            num_alerts = len(alerts)

                            st.subheader(subcat)
                            st.metric(label="Nombre d'articles", value=num_items)
                            st.metric(label="Articles en alerte", value=f"{'⚠️ ' if num_alerts > 0 else ''}{num_alerts}")

                            if st.button(f"Consulter {subcat}", key=f"subcat_{subcat}", use_container_width=True):
                                st.session_state.selected_subcategory = subcat
                                st.rerun()
        # Pour les autres catégories, on affiche directement les produits
        else:
            st.subheader(f"Articles pour : {category}")
            product_df = df[df['categorie'] == category].sort_values(by='nom')

            if product_df.empty:
                st.info(f"Aucun article dans cette catégorie.")
            else:
                cols = st.columns(2)
                for i, row in product_df.iterrows():
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.subheader(f"{row.get('emoji', '📦')} {row['nom']}")
                            if row['quantite'] < row['seuil_alerte']:
                                st.markdown(f"⚠️ <span style='color:red;'>Seuil bas ({row['seuil_alerte']})</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"Seuil d'alerte : {row['seuil_alerte']}")
                            
                            if user_role in ['AdminBenevoles', 'Super Admin']:
                                st.metric(label="Quantité en stock", value=row['quantite'])
                                if st.button(" Modifier", key=f"edit_{row['id']}", use_container_width=True):
                                    admin_stock_change_dialog(user_id, row['id'], row['nom'], row['quantite'])
                            else:
                                st.metric(label="Quantité en stock", value=row['quantite'])
                                if st.button("Demander une modification", key=f"request_{row['id']}"):
                                    request_stock_change_dialog(user_id, row['id'], row['nom'], row['quantite'])

    # --- Vue 1: Affichage des catégories principales ---
    else:
        if df.empty:
            st.info("Aucun article en stock. Allez dans l'onglet 'Administration' pour en ajouter.")

        col1, col2 = st.columns(2)
        grid_cols = [col1, col2] * ((len(CATEGORIES) + 1) // 2)

        for i, category in enumerate(CATEGORIES.keys()):
            with grid_cols[i]:
                with st.container(border=True):
                    category_df = df[df['categorie'] == category]
                    num_items = len(category_df)
                    alerts = category_df[category_df['quantite'] < category_df['seuil_alerte']]
                    num_alerts = len(alerts)

                    st.subheader(f"{ICONS.get(category, '📦')} {category}")
                    st.metric(label="Nombre d'articles", value=num_items)
                    st.metric(label="Articles en alerte", value=f"{'⚠️ ' if num_alerts > 0 else ''}{num_alerts}")

                    if st.button(f"Gérer {category}", key=f"cat_{category}", use_container_width=True):
                        st.session_state.selected_category = category
                        st.rerun()
