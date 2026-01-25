import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
from logger_config import logger
import zipfile
import io
import time

# Configuration
DATABASE_NAME = 'data/stock_kouttab.db'

def export_database_to_csv():
    """
    Exporte toutes les tables de la base de données vers des fichiers CSV.
    Retourne un dictionnaire avec les noms des tables et leurs DataFrames.
    """
    try:
        # Créer le répertoire data s'il n'existe pas
        data_dir = os.path.dirname(DATABASE_NAME)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Répertoire '{data_dir}' créé.")
        
        # Vérifier si le fichier de base de données existe
        if not os.path.exists(DATABASE_NAME):
            logger.error(f"Le fichier de base de données '{DATABASE_NAME}' n'existe pas.")
            st.error(f"Le fichier de base de données '{DATABASE_NAME}' n'existe pas.")
            return None
        
        conn = sqlite3.connect(DATABASE_NAME)
        
        # Récupérer la liste de toutes les tables sauf Admins
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'Admins';")
        tables = cursor.fetchall()
        
        logger.info(f"Tables trouvées dans la base de données: {[table[0] for table in tables]}")
        
        if not tables:
            logger.warning("Aucune table trouvée dans la base de données.")
            st.warning("Aucune table trouvée dans la base de données. La base de données est peut-être vide.")
            conn.close()
            return {}
        
        exported_data = {}
        
        for table_name, in tables:
            try:
                # Vérifier si la table a des données
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                if row_count > 0:
                    # Exporter chaque table en CSV
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    exported_data[table_name] = df
                    logger.info(f"Table '{table_name}' exportée: {row_count} lignes")
                else:
                    logger.info(f"Table '{table_name}' est vide, ignorée")
                    # Exporter quand même les tables vides pour la structure
                    df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 0", conn)
                    exported_data[table_name] = df
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'export de la table '{table_name}': {e}")
                st.error(f"Erreur lors de l'export de la table '{table_name}': {e}")
                continue
            
        conn.close()
        logger.info(f"Base de données exportée avec succès. {len(exported_data)} tables exportées.")
        return exported_data
        
    except Exception as e:
        logger.error(f"Erreur lors de l'export de la base de données: {e}")
        st.error(f"Erreur lors de l'export: {e}")
        return None

def create_export_zip(exported_data):
    """
    Crée un fichier ZIP contenant tous les fichiers CSV exportés.
    """
    try:
        # Créer un buffer en mémoire pour le ZIP
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for table_name, df in exported_data.items():
                # Convertir le DataFrame en CSV
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8')
                csv_buffer.seek(0)
                
                # Ajouter le fichier CSV au ZIP
                zip_file.writestr(f"{table_name}.csv", csv_buffer.getvalue())
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du ZIP: {e}")
        st.error(f"Erreur lors de la création du ZIP: {e}")
        return None

def import_database_from_csv(uploaded_files):
    """
    Importe les données depuis des fichiers CSV vers la base de données.
    """
    try:
        if not uploaded_files:
            st.error("Veuillez sélectionner des fichiers CSV à importer.")
            return False
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        errors = []
        
        for uploaded_file in uploaded_files:
            try:
                # Récupérer le nom de la table à partir du nom du fichier
                table_name = os.path.splitext(uploaded_file.name)[0]
                
                # Ignorer la table Admins pour des raisons de sécurité
                if table_name == 'Admins':
                    logger.warning(f"Table 'Admins' ignorée pour des raisons de sécurité")
                    continue
                
                # Lire le fichier CSV
                df = pd.read_csv(uploaded_file)
                
                # Vider la table existante (optionnel - à confirmer avec l'utilisateur)
                cursor.execute(f"DELETE FROM {table_name}")
                
                # Insérer les données
                df.to_sql(table_name, conn, if_exists='append', index=False)
                
                success_count += 1
                logger.info(f"Table {table_name} importée avec succès ({len(df)} lignes)")
                
            except Exception as e:
                error_count += 1
                error_msg = f"Erreur lors de l'import de {uploaded_file.name}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        conn.commit()
        conn.close()
        
        # Afficher les résultats
        if success_count > 0:
            st.success(f"✅ {success_count} table(s) importée(s) avec succès")
        
        if error_count > 0:
            st.error(f"❌ {error_count} erreur(s) d'import:")
            for error in errors:
                st.error(f"• {error}")
        
        return success_count > 0 and error_count == 0
        
    except Exception as e:
        logger.error(f"Erreur générale lors de l'import: {e}")
        st.error(f"Erreur générale lors de l'import: {e}")
        return False

def check_database_status():
    """
    Vérifie l'état de la base de données et retourne des informations diagnostiques.
    """
    try:
        # Créer le répertoire data s'il n'existe pas
        data_dir = os.path.dirname(DATABASE_NAME)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Répertoire '{data_dir}' créé.")
        
        if not os.path.exists(DATABASE_NAME):
            return {
                'exists': False,
                'size': 0,
                'tables': [],
                'error': f"Le fichier '{DATABASE_NAME}' n'existe pas",
                'permissions': None
            }
        
        # Obtenir la taille du fichier
        file_size = os.path.getsize(DATABASE_NAME)
        
        # Vérifier les permissions du fichier
        try:
            file_permissions = oct(os.stat(DATABASE_NAME).st_mode)[-3:]
            can_write = os.access(DATABASE_NAME, os.W_OK)
            can_read = os.access(DATABASE_NAME, os.R_OK)
        except Exception as e:
            file_permissions = f"Erreur: {e}"
            can_write = False
            can_read = False
        
        # Vérifier si le fichier est verrouillé ou en lecture seule
        is_locked = not can_write
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Lister les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        table_info = []
        total_rows = 0
        
        for table_name, in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                total_rows += row_count
                table_info.append({
                    'name': table_name,
                    'rows': row_count
                })
            except Exception as e:
                table_info.append({
                    'name': table_name,
                    'rows': 0,
                    'error': str(e)
                })
        
        conn.close()
        
        return {
            'exists': True,
            'size': file_size,
            'tables': table_info,
            'total_tables': len(tables),
            'total_rows': total_rows,
            'permissions': file_permissions,
            'can_write': can_write,
            'can_read': can_read,
            'is_locked': is_locked
        }
        
    except Exception as e:
        return {
            'exists': False,
            'size': 0,
            'tables': [],
            'error': f"Erreur de diagnostic: {e}",
            'permissions': None
        }

def force_database_initialization():
    """
    Force l'initialisation complète de la base de données avec toutes les tables.
    Version détaillée avec débogage et gestion des permissions.
    """
    try:
        import sqlite3
        from database import DATABASE_NAME, UPLOADS_DIR
        import os
        import tempfile
        
        st.warning("🔄 Tentative de réinitialisation détaillée de la base de données...")
        
        # Étape 1: Vérifier et créer le répertoire uploads
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)
            logger.info(f"Répertoire '{UPLOADS_DIR}' créé.")
        
        # Étape 2: Créer le répertoire data s'il n'existe pas
        data_dir = os.path.dirname(DATABASE_NAME)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Répertoire '{data_dir}' créé.")
        
        # Étape 3: Gérer les permissions et créer la base de données
        db_path = DATABASE_NAME
        
        # Si le fichier existe mais est verrouillé, essayer de le recréer
        if os.path.exists(db_path):
            try:
                # Tester l'écriture
                test_conn = sqlite3.connect(db_path)
                test_conn.execute("SELECT 1")
                test_conn.close()
                logger.info("Base de données existante accessible en écriture")
            except Exception as e:
                logger.warning(f"Base de données existante inaccessible: {e}")
                # Sauvegarder l'ancien fichier et en créer un nouveau
                backup_path = f"{db_path}.backup_{int(time.time())}"
                try:
                    os.rename(db_path, backup_path)
                    logger.info(f"Ancienne base de données sauvegardée dans: {backup_path}")
                    st.info(f"📁 Ancienne BDD sauvegardée dans: {backup_path}")
                except Exception as backup_error:
                    logger.error(f"Impossible de sauvegarder l'ancienne BDD: {backup_error}")
        
        # Étape 3: Connexion et création manuelle des tables
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Activer les clés étrangères
        c.execute("PRAGMA foreign_keys = ON")
        
        tables_to_create = [
            # Table Stock
            ('''CREATE TABLE IF NOT EXISTS Stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nom TEXT NOT NULL UNIQUE, 
                categorie TEXT NOT NULL,
                sous_categorie TEXT,
                quantite INTEGER NOT NULL, 
                seuil_alerte INTEGER NOT NULL, 
                emoji TEXT NOT NULL DEFAULT '📦',
                alert_sent BOOLEAN NOT NULL DEFAULT 0
            )''', 'Stock'),
            
            # Table SousCategories
            ('''CREATE TABLE IF NOT EXISTS SousCategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_categorie TEXT NOT NULL,
                nom_sous_categorie TEXT NOT NULL,
                UNIQUE(nom_categorie, nom_sous_categorie)
            )''', 'SousCategories'),
            
            # Table Admins
            ('''CREATE TABLE IF NOT EXISTS Admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                username TEXT NOT NULL UNIQUE, 
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL, 
                validation_status TEXT NOT NULL DEFAULT 'pending',
                nom TEXT, 
                prenom TEXT, 
                email TEXT, 
                telephone TEXT, 
                rib TEXT
            )''', 'Admins'),
            
            # Table NotesDeFrais
            ('''CREATE TABLE IF NOT EXISTS NotesDeFrais (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                id_user INTEGER NOT NULL,
                date_depense TEXT NOT NULL, 
                rattachement TEXT NOT NULL, 
                fournisseur TEXT,
                nature_charge TEXT, 
                montant REAL NOT NULL, 
                commentaires TEXT,
                remboursement_deja_emis REAL DEFAULT 0, 
                remise REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'En attente', 
                commentaires_compta TEXT,
                date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''', 'NotesDeFrais'),
            
            # Table FichiersNotesDeFrais
            ('''CREATE TABLE IF NOT EXISTS FichiersNotesDeFrais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_note_de_frais INTEGER NOT NULL,
                nom_fichier TEXT NOT NULL
            )''', 'FichiersNotesDeFrais'),
            
            # Table Factures
            ('''CREATE TABLE IF NOT EXISTS Factures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user INTEGER NOT NULL,
                date_depot TEXT NOT NULL,
                commentaire TEXT,
                status TEXT NOT NULL DEFAULT 'En attente',
                commentaires_compta TEXT,
                date_depot TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''', 'Factures'),
            
            # Table FichiersFactures
            ('''CREATE TABLE IF NOT EXISTS FichiersFactures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_facture INTEGER NOT NULL,
                nom_fichier TEXT NOT NULL
            )''', 'FichiersFactures'),
            
            # Table StockModifications
            ('''CREATE TABLE IF NOT EXISTS StockModifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user INTEGER NOT NULL,
                id_stock INTEGER NOT NULL,
                quantite_actuelle INTEGER NOT NULL,
                quantite_demandee INTEGER NOT NULL,
                date_demande TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'En attente'
            )''', 'StockModifications')
        ]
        
        created_tables = []
        errors = []
        
        for sql_query, table_name in tables_to_create:
            try:
                c.execute(sql_query)
                created_tables.append(table_name)
                logger.info(f"Table '{table_name}' créée avec succès")
            except Exception as e:
                error_msg = f"Erreur création table '{table_name}': {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Étape 4: Insérer les données par défaut
        try:
            default_categories = {
                "Nourriture": ["Snacks", "Boissons", "Fruits", "Produits laitiers"],
                "Fournitures": ["Stylos", "Cahiers", "Classeurs", "Autres"],
                "Intendance": ["Produits ménagers", "Papier toilette", "Savon", "Autres"],
                "Bibliothèque": ["Livres", "Magazines", "Cahiers d'activités", "Autres"]
            }
            
            for cat, subcats in default_categories.items():
                for subcat in subcats:
                    c.execute("INSERT OR IGNORE INTO SousCategories (nom_categorie, nom_sous_categorie) VALUES (?, ?)", (cat, subcat))
            
            logger.info("Catégories par défaut insérées")
            
        except Exception as e:
            error_msg = f"Erreur insertion catégories: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        conn.commit()
        conn.close()
        
        # Étape 5: Vérification finale
        status = check_database_status()
        
        if status['total_tables'] > 0:
            st.success(f"✅ Base de données initialisée avec succès ! {status['total_tables']} tables créées.")
            logger.info(f"Base de données réinitialisée: {status['total_tables']} tables créées")
            
            # Afficher les détails
            st.info("📋 **Tables créées:**")
            for table in status['tables']:
                st.write(f"✅ {table['name']}: {table['rows']} lignes")
            
            # Afficher les permissions
            if status['permissions']:
                st.info(f"🔒 Permissions du fichier: {status['permissions']}")
                st.write(f"📖 Lecture: {'✅' if status['can_read'] else '❌'}")
                st.write(f"✏️ Écriture: {'✅' if status['can_write'] else '❌'}")
            
            return True
        else:
            st.error("❌ L'initialisation a échoué. Aucune table créée.")
            if errors:
                st.error("Erreurs rencontrées:")
                for error in errors:
                    st.error(f"• {error}")
            logger.error("Échec de l'initialisation de la base de données")
            return False
            
    except Exception as e:
        st.error(f"❌ Erreur générale lors de l'initialisation: {e}")
        logger.error(f"Erreur générale lors de la réinitialisation de la BDD: {e}")
        return False

def display_database_export_import_page():
    """
    Affiche la page d'export/import de la base de données.
    """
    st.header("🗄️ Export/Import de la Base de Données")
    
    # Vérifier que l'utilisateur est Super Admin
    if st.session_state.get('user_role') != 'Super Admin':
        st.error("⚠️ Cette fonctionnalité est réservée aux Super Admins uniquement.")
        return
    
    # Section de diagnostic
    st.subheader("🔍 Diagnostic de la base de données")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔎 Vérifier l'état de la base de données"):
            with st.spinner("Analyse en cours..."):
                status = check_database_status()
                
                if 'error' in status:
                    st.error(f"❌ {status['error']}")
                else:
                    st.info("📊 **État de la base de données:**")
                    col1_1, col1_2, col1_3 = st.columns(3)
                    with col1_1:
                        st.metric("📁 Fichier existe", "✅ Oui" if status['exists'] else "❌ Non")
                    with col1_2:
                        st.metric("📊 Tables", status['total_tables'])
                    with col1_3:
                        st.metric("📝 Lignes totales", status['total_rows'])
                    
                    if status['exists']:
                        st.metric("💾 Taille", f"{status['size'] / 1024:.2f} KB")
                    
                    if status['tables']:
                        st.write("**Détail des tables:**")
                        for table in status['tables']:
                            if 'error' in table:
                                st.error(f"❌ {table['name']}: {table['error']}")
                            else:
                                st.write(f"📋 {table['name']}: {table['rows']} lignes")
                    
                    # Si aucune table trouvée, proposer l'initialisation
                    if status['total_tables'] == 0:
                        st.warning("⚠️ **Aucune table trouvée!** La base de données doit être initialisée.")
    
    with col2:
        if st.button("🔄 Forcer l'initialisation de la BDD", type="secondary"):
            with st.spinner("Initialisation en cours..."):
                success = force_database_initialization()
                if success:
                    # Rafraîchir automatiquement le diagnostic
                    st.rerun()
    
    st.markdown("---")
    
    # Onglets pour Export et Import
    export_tab, import_tab = st.tabs(["📤 Exporter la BDD", "📥 Importer la BDD"])
    
    with export_tab:
        st.subheader("📤 Exporter la base de données")
        st.write("""
        Exportez toutes les données de la base de données au format CSV.
        Cela crée un fichier ZIP contenant un fichier CSV par table.
        
        ⚠️ **Note:** La table `Admins` n'est pas exportée pour des raisons de sécurité.
        """)
        
        if st.button("🚀 Exporter la base de données", type="primary"):
            with st.spinner("Export en cours..."):
                exported_data = export_database_to_csv()
                
                if exported_data:
                    # Créer le fichier ZIP
                    zip_data = create_export_zip(exported_data)
                    
                    if zip_data:
                        # Préparer le nom du fichier
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"stock_kouttab_backup_{timestamp}.zip"
                        
                        # Offrir le téléchargement
                        st.download_button(
                            label="📥 Télécharger l'export",
                            data=zip_data,
                            file_name=filename,
                            mime="application/zip",
                            help="Cliquez pour télécharger le fichier ZIP contenant tous les exports CSV"
                        )
                        
                        st.success(f"✅ Export réussi ! {len(exported_data)} tables exportées.")
                        
                        # Afficher un aperçu des données exportées
                        st.subheader("📊 Aperçu des données exportées:")
                        for table_name, df in exported_data.items():
                            with st.expander(f"📋 {table_name} ({len(df)} lignes)"):
                                st.dataframe(df.head(5))
        
        # Informations supplémentaires
        with st.expander("ℹ️ Informations sur l'export"):
            st.write("""
            **Tables exportées:**
            - Stock: Articles et quantités
            - SousCategories: Catégories et sous-catégories  
            - NotesDeFrais: Notes de frais
            - FichiersNotesDeFrais: Pièces jointes des notes de frais
            - Factures: Factures déposées
            - FichiersFactures: Pièces jointes des factures
            - StockModifications: Historique des modifications
            
            ⚠️ **La table Admins n'est pas exportée/importée pour des raisons de sécurité**
            
            **Format:** Fichier ZIP contenant des fichiers CSV
            **Encodage:** UTF-8
            **Compression:** ZIP (réduction de taille)
            """)
    
    with import_tab:
        st.subheader("📥 Importer la base de données")
        st.warning("""
        ⚠️ **ATTENTION:** L'import va **remplacer** toutes les données existantes dans les tables correspondantes.
        Il est recommandé de faire un backup avant d'importer.
        
        🔒 **Sécurité:** La table `Admins` est automatiquement ignorée lors de l'import.
        """)
        
        # Confirmation de sécurité
        confirm_import = st.checkbox("🔒 Je comprends que cela remplacera les données existantes", key="confirm_import")
        
        if confirm_import:
            uploaded_files = st.file_uploader(
                "📁 Sélectionnez les fichiers CSV à importer",
                type=['csv'],
                accept_multiple_files=True,
                help="Sélectionnez un ou plusieurs fichiers CSV exportés précédemment"
            )
            
            if uploaded_files:
                st.write(f"📎 {len(uploaded_files)} fichier(s) sélectionné(s):")
                for file in uploaded_files:
                    st.write(f"• {file.name} ({file.size} octets)")
                
                if st.button("🚀 Importer les données", type="primary"):
                    with st.spinner("Import en cours..."):
                        success = import_database_from_csv(uploaded_files)
                        
                        if success:
                            st.success("✅ Import terminé avec succès !")
                            st.info("🔄 Veuillez rafraîchir la page pour voir les changements.")
                        else:
                            st.error("❌ Des erreurs sont survenues lors de l'import.")
        
        else:
            st.info("🔒 Cochez la case de confirmation pour pouvoir importer des données.")
        
        # Instructions
        with st.expander("📖 Instructions d'import"):
            st.write("""
            **Étapes pour importer:**
            1. Cochez la case de confirmation (sécurité)
            2. Sélectionnez les fichiers CSV exportés précédemment
            3. Cliquez sur "Importer les données"
            4. Attendez la fin du traitement
            
            **Important:**
            - Les fichiers doivent être au format CSV exactement comme exportés
            - Les noms de fichiers doivent correspondre aux noms des tables
            - L'import remplace les données existantes
            - Faites toujours un backup avant d'importer
            """)

# Fonction utilitaire pour vérifier l'intégrité des fichiers
def validate_csv_files(uploaded_files):
    """
    Valide que les fichiers CSV sont corrects pour l'import.
    """
    required_tables = [
        'Stock', 'SousCategories', 'Admins', 'NotesDeFrais', 
        'FichiersNotesDeFrais', 'Factures', 'FichiersFactures', 
        'StockModifications'
    ]
    
    uploaded_tables = []
    for file in uploaded_files:
        table_name = os.path.splitext(file.name)[0]
        uploaded_tables.append(table_name)
    
    missing_tables = set(required_tables) - set(uploaded_tables)
    extra_tables = set(uploaded_tables) - set(required_tables)
    
    return {
        'missing_tables': list(missing_tables),
        'extra_tables': list(extra_tables),
        'is_valid': len(missing_tables) == 0
    }
