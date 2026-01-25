import streamlit as st
import pandas as pd
from database import import_inventory_from_csv
from logger_config import logger


def display_csv_import():
    st.write("#### Importer un inventaire depuis un fichier CSV")

    st.info("""
    **Format du fichier CSV requis :**
    - Colonnes : Catégorie, Sous-catégorie, Nom de l'article, Quantité initiale
    - Les données doivent commencer à partir de la ligne 7 (lignes 1-6 ignorées)
    - Les articles existants seront ignorés
    - Les sous-catégories seront créées automatiquement
    """)

    uploaded_file = st.file_uploader(
        "Choisissez un fichier CSV",
        type=['csv'],
        help="Le fichier doit contenir les colonnes : Catégorie, Sous-catégorie, Nom de l'article, Quantité initiale"
    )

    if uploaded_file is not None:
        try:
            # Lire le fichier CSV en ignorant les 6 premières lignes
            csv_data = pd.read_csv(uploaded_file, skiprows=6)

            # Afficher un aperçu des données
            st.write("📋 Aperçu des données à importer :")
            st.dataframe(csv_data.head(10))

            # Vérifier les colonnes requises
            required_columns = ['Catégorie', 'Sous-catégorie', 'Nom de l\'article', 'Quantité initiale']
            missing_columns = [col for col in required_columns if col not in csv_data.columns]

            if missing_columns:
                st.error(f"Colonnes manquantes dans le fichier CSV : {', '.join(missing_columns)}")
                return

            st.write(f"📊 **Statistiques de l'importation :**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total des lignes", len(csv_data))
            with col2:
                st.metric("Articles uniques", csv_data['Nom de l\'article'].nunique())
            with col3:
                st.metric("Catégories", csv_data['Catégorie'].nunique())

            # Bouton d'importation
            if st.button("🚀 Lancer l'importation", type="primary"):
                with st.spinner("Importation en cours..."):
                    result = import_inventory_from_csv(csv_data)

                    if result:
                        st.success("✅ Importation terminée !")

                        # Afficher les résultats
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Articles importés", result['imported'], delta=None)
                        with col2:
                            st.metric("Articles ignorés", result['skipped'], delta=None)
                        with col3:
                            st.metric("Erreurs", len(result['errors']), delta=None)

                        # Afficher les erreurs s'il y en a
                        if result['errors']:
                            st.write("⚠️ **Erreurs rencontrées :**")
                            for error in result['errors'][:10]:  # Limiter à 10 erreurs
                                st.error(error)
                            if len(result['errors']) > 10:
                                st.warning(f"... et {len(result['errors']) - 10} autres erreurs")

                        if result['imported'] > 0:
                            st.balloons()
                            st.success(f"🎉 {result['imported']} articles ont été importés avec succès !")
                    else:
                        st.error("❌ Erreur lors de l'importation. Vérifiez le format de votre fichier.")

        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier CSV : {str(e)}")
            st.info("Assurez-vous que le fichier est bien au format CSV et que les 6 premières lignes sont ignorées.")