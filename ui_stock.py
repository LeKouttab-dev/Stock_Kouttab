import streamlit as st
import pandas as pd
from database import get_all_items, update_quantity, create_stock_modification_request

@st.dialog("Demande de modification de stock")
def request_stock_change_dialog(user_id, item_id, item_name, current_qty):
    st.write(f"Vous demandez à modifier la quantité pour **{item_name}**.")
    st.write(f"Quantité actuelle : **{current_qty}**")
    
    # Utiliser st.session_state pour gérer l'état de la soumission dans le dialogue
    if 'request_sent_in_dialog' not in st.session_state:
        st.session_state.request_sent_in_dialog = False

    if st.session_state.request_sent_in_dialog:
        st.success("✅ Votre demande a été envoyée pour validation.")
        if st.button("Fermer"):
            st.session_state.request_sent_in_dialog = False # Réinitialiser pour la prochaine fois
            st.rerun() # Rerun pour fermer le dialogue
    else:
        requested_qty = st.number_input("Nouvelle quantité souhaitée", min_value=0, value=current_qty, key="requested_qty_dialog")
        if st.button("Envoyer la demande"):
            create_stock_modification_request(user_id, item_id, current_qty, requested_qty)
            st.session_state.request_sent_in_dialog = True
            st.rerun() # Rerun pour afficher le message de succès dans le dialogue

def display_stock_management(user_id, user_role):
    st.header("Tableau de Bord du Stock")

    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None

    if st.session_state.selected_category:
        if st.button("⬅️ Retour aux catégories"):
            st.session_state.selected_category = None
            st.rerun()

        category = st.session_state.selected_category
        st.subheader(f"Détails de la catégorie : {category}")
        df = get_all_items()
        category_df = df[df['categorie'] == category].sort_values(by='nom')

        if category_df.empty:
            st.info(f"Aucun article dans la catégorie '{category}'.")
        else:
            cols = st.columns(2)
            for i, row in category_df.iterrows():
                with cols[i % 2]:
                    with st.container(border=True):
                        st.subheader(f"{row.get('emoji', '📦')} {row['nom']}")
                        
                        if row['quantite'] < row['seuil_alerte']:
                            st.markdown(f"⚠️ <span style='color:red;'>Seuil bas ({row['seuil_alerte']})</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"Seuil d'alerte : {row['seuil_alerte']}")

                        # Logique de modification par rôle
                        if user_role in ['AdminBenevoles', 'Super Admin']:
                            # Modification directe pour les admins
                            new_qty = st.number_input("Quantité", value=row['quantite'], min_value=0, key=f"direct_edit_{row['id']}")
                            if new_qty != row['quantite']:
                                update_quantity(row['id'], new_qty) # Correction ici
                                st.rerun()
                        else: # Logique de demande pour les Benevoles
                            st.metric(label="Quantité en stock", value=row['quantite'])
                            if st.button("Demander une modification", key=f"request_{row['id']}"):
                                request_stock_change_dialog(user_id, row['id'], row['nom'], row['quantite'])
    else:
        df = get_all_items()
        categories = ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"]
        icons = {"Nourriture": "🍔", "Fournitures": "📝", "Intendance": "🧼", "Bibliothèque": "📚"}

        col1, col2 = st.columns(2)
        grid_cols = [col1, col2, col1, col2]

        for i, category in enumerate(categories):
            with grid_cols[i]:
                with st.container(border=True):
                    category_df = df[df['categorie'] == category]
                    num_items = len(category_df)
                    alerts = category_df[category_df['quantite'] < category_df['seuil_alerte']]
                    num_alerts = len(alerts)

                    st.subheader(f"{icons.get(category, '📦')} {category}")
                    st.metric(label="Nombre d'articles", value=num_items)
                    st.metric(label="Articles en alerte", value=f"{'⚠️ ' if num_alerts > 0 else ''}{num_alerts}")

                    if st.button(f"Consulter la catégorie", key=f"cat_{category}", use_container_width=True):
                        st.session_state.selected_category = category
                        st.rerun()
