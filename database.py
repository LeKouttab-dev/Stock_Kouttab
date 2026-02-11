import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime
import os
from email_utils import send_alert_email, send_new_expense_alert_email
from logger_config import logger
from environment import env

# --- Configuration ---
DATABASE_NAME = 'stock_kouttab.db'
UPLOADS_DIR = 'uploads'

# --- Fonctions de Hachage ---
import hashlib
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password_hash, provided_password):
    return stored_password_hash == hash_password(provided_password)

# --- Fonctions de Base de Données ---
def init_db():
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE, categorie TEXT NOT NULL,
            sous_categorie TEXT,
            quantite INTEGER NOT NULL, seuil_alerte INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '📦',
            alert_sent BOOLEAN NOT NULL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS SousCategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_categorie TEXT NOT NULL,
            nom_sous_categorie TEXT NOT NULL,
            UNIQUE(nom_categorie, nom_sous_categorie)
        )
    ''')
    # ... (autres tables)
    c.execute('''
        CREATE TABLE IF NOT EXISTS Admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            role TEXT NOT NULL, validation_status TEXT NOT NULL DEFAULT 'pending',
            nom TEXT, prenom TEXT, email TEXT, telephone TEXT, rib TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS NotesDeFrais (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_user INTEGER NOT NULL,
            date_depense TEXT NOT NULL, rattachement TEXT NOT NULL, fournisseur TEXT,
            nature_charge TEXT, montant REAL NOT NULL, commentaires TEXT,
            remboursement_deja_emis REAL DEFAULT 0, remise REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'En attente', commentaires_compta TEXT,
            date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_user) REFERENCES Admins (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS FichiersNotesDeFrais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_note_de_frais INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            FOREIGN KEY (id_note_de_frais) REFERENCES NotesDeFrais (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS Factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            commentaire TEXT,
            date_depot TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            statut TEXT NOT NULL DEFAULT 'En attente',
            FOREIGN KEY (id_user) REFERENCES Admins (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS FichiersFactures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_facture INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            chemin_fichier TEXT NOT NULL,
            FOREIGN KEY (id_facture) REFERENCES Factures (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS StockModifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER NOT NULL,
            id_stock INTEGER NOT NULL,
            quantite_actuelle INTEGER NOT NULL,
            quantite_demandee INTEGER NOT NULL,
            date_demande TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'En attente',
            FOREIGN KEY (id_user) REFERENCES Admins (id),
            FOREIGN KEY (id_stock) REFERENCES Stock (id)
        )
    ''')
    
    # Initialisation des données
    c.execute("SELECT * FROM Admins WHERE role = 'Super Admin'")
    if c.fetchone() is None:
        c.execute("INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', hash_password('kouttab_admin'), 'Super Admin', 'active', 'Admin', 'Principal', 'admin@example.com'))
        logger.info("Compte Super Admin par défaut créé.")

    # Initialisation des sous-catégories par défaut
    default_categories = {
        "Nourriture": ["Sucré", "Salé"],
        "Fournitures": ["Papeterie", "Matériel Pédagogique"],
        "Intendance": ["Produits d'entretien", "Consommables"],
        "Bibliothèque": ["Livres", "Manuels"]
    }
    for cat, subcats in default_categories.items():
        for subcat in subcats:
            c.execute("INSERT OR IGNORE INTO SousCategories (nom_categorie, nom_sous_categorie) VALUES (?, ?)", (cat, subcat))

    conn.commit()
    conn.close()
    logger.info("Base de données initialisée.")

# --- Fonctions pour les Factures ---
def add_invoice(user_id, user_full_name, commentaire, uploaded_files):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Utiliser le nom du premier fichier comme nom principal de la facture
        nom_facture = uploaded_files[0].name if uploaded_files else "Facture sans nom"
        
        # Créer l'entrée de facture principale
        c.execute("""
            INSERT INTO Factures (id_user, nom_fichier, commentaire) VALUES (?, ?, ?)
        """, (user_id, nom_facture, commentaire))
        
        facture_id = c.lastrowid
        
        # Sauvegarder les fichiers
        for file in uploaded_files:
            # Créer le répertoire uploads s'il n'existe pas
            if not os.path.exists(UPLOADS_DIR):
                os.makedirs(UPLOADS_DIR)
            
            # Sauvegarder le fichier
            file_path = os.path.join(UPLOADS_DIR, f"{facture_id}_{file.name}")
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            
            # Enregistrer le fichier dans la base de données
            c.execute("""
                INSERT INTO FichiersFactures (id_facture, nom_fichier, chemin_fichier) 
                VALUES (?, ?, ?)
            """, (facture_id, file.name, file_path))
        
        conn.commit()
        logger.info(f"Facture ID {facture_id} ajoutée par '{user_full_name}' avec {len(uploaded_files)} fichier(s).")
        return facture_id
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la facture: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_all_invoices():
    conn = sqlite3.connect(env.get_database_path())
    query = """
        SELECT f.*, a.nom, a.prenom, 
               GROUP_CONCAT(ff.nom_fichier, ', ') as fichiers_noms,
               COUNT(ff.id) as nombre_fichiers
        FROM Factures f 
        JOIN Admins a ON f.id_user = a.id 
        LEFT JOIN FichiersFactures ff ON f.id = ff.id_facture
        GROUP BY f.id
        ORDER BY f.date_depot DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_invoice_files(invoice_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("""
        SELECT nom_fichier, chemin_fichier 
        FROM FichiersFactures 
        WHERE id_facture = ?
        ORDER BY nom_fichier
    """, (invoice_id,))
    files = c.fetchall()
    conn.close()
    return files

def update_invoice_status(invoice_id, new_status):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE Factures 
            SET statut = ? 
            WHERE id = ?
        """, (new_status, invoice_id))
        conn.commit()
        logger.info(f"Statut de la facture ID {invoice_id} mis à jour vers '{new_status}'.")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du statut de la facture: {e}")
        return False
    finally:
        conn.close()

# --- Fonctions pour la gestion des catégories et sous-catégories ---
def get_all_categories():
    """Récupère toutes les catégories uniques de la table Stock"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT DISTINCT categorie FROM Stock ORDER BY categorie")
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    return categories

def get_all_subcategories():
    """Récupère toutes les sous-catégories"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT id, nom_categorie, nom_sous_categorie FROM SousCategories ORDER BY nom_categorie, nom_sous_categorie")
    subcategories = c.fetchall()
    conn.close()
    return subcategories

def update_category(old_name, new_name):
    """Met à jour une catégorie dans tous les articles concernés"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Mettre à jour la catégorie dans la table Stock
        c.execute("UPDATE Stock SET categorie = ? WHERE categorie = ?", (new_name, old_name))
        
        # Mettre à jour les sous-catégories associées
        c.execute("UPDATE SousCategories SET nom_categorie = ? WHERE nom_categorie = ?", (new_name, old_name))
        
        conn.commit()
        logger.info(f"Catégorie '{old_name}' renommée en '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la catégorie: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_category(category_name):
    """Supprime une catégorie et ses sous-catégories"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Vérifier s'il y a des articles dans cette catégorie
        c.execute("SELECT COUNT(*) FROM Stock WHERE categorie = ?", (category_name,))
        count = c.fetchone()[0]
        
        if count > 0:
            logger.warning(f"Tentative de suppression de la catégorie '{category_name}' contenant {count} articles")
            return False, f"Impossible de supprimer : {count} article(s) dans cette catégorie"
        
        # Supprimer les sous-catégories associées
        c.execute("DELETE FROM SousCategories WHERE nom_categorie = ?", (category_name,))
        
        conn.commit()
        logger.info(f"Catégorie '{category_name}' et ses sous-catégories supprimées")
        return True, "Catégorie supprimée avec succès"
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la catégorie: {e}")
        conn.rollback()
        return False, f"Erreur lors de la suppression: {str(e)}"
    finally:
        conn.close()

def update_subcategory(subcategory_id, new_category, new_name):
    """Met à jour une sous-catégorie"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Mettre à jour la sous-catégorie
        c.execute("UPDATE SousCategories SET nom_categorie = ?, nom_sous_categorie = ? WHERE id = ?", 
                 (new_category, new_name, subcategory_id))
        
        # Mettre à jour les articles concernés
        c.execute("UPDATE Stock SET categorie = ?, sous_categorie = ? WHERE sous_categorie = (SELECT nom_sous_categorie FROM SousCategories WHERE id = ?)", 
                 (new_category, new_name, subcategory_id))
        
        conn.commit()
        logger.info(f"Sous-catégorie ID {subcategory_id} mise à jour")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la sous-catégorie: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_subcategory(subcategory_id):
    """Supprime une sous-catégorie"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Récupérer le nom de la sous-catégorie
        c.execute("SELECT nom_sous_categorie FROM SousCategories WHERE id = ?", (subcategory_id,))
        result = c.fetchone()
        if not result:
            return False, "Sous-catégorie non trouvée"
        
        subcat_name = result[0]
        
        # Vérifier s'il y a des articles avec cette sous-catégorie
        c.execute("SELECT COUNT(*) FROM Stock WHERE sous_categorie = ?", (subcat_name,))
        count = c.fetchone()[0]
        
        if count > 0:
            logger.warning(f"Tentative de suppression de la sous-catégorie '{subcat_name}' contenant {count} articles")
            return False, f"Impossible de supprimer : {count} article(s) dans cette sous-catégorie"
        
        # Supprimer la sous-catégorie
        c.execute("DELETE FROM SousCategories WHERE id = ?", (subcategory_id,))
        
        conn.commit()
        logger.info(f"Sous-catégorie '{subcat_name}' supprimée")
        return True, "Sous-catégorie supprimée avec succès"
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la sous-catégorie: {e}")
        conn.rollback()
        return False, f"Erreur lors de la suppression: {str(e)}"
    finally:
        conn.close()

def add_category(category_name):
    """Ajoute une nouvelle catégorie"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        # Vérifier si la catégorie existe déjà
        c.execute("SELECT COUNT(*) FROM Stock WHERE categorie = ?", (category_name,))
        if c.fetchone()[0] > 0:
            return False, "Cette catégorie existe déjà"
        
        # Ajouter un article fictif pour créer la catégorie
        c.execute("""
            INSERT INTO Stock (nom, categorie, quantite, seuil_alerte, emoji) 
            VALUES (?, ?, 0, 5, '📦')
        """, (f"_TEMP_{category_name}", category_name))
        
        # Supprimer immédiatement l'article temporaire
        c.execute("DELETE FROM Stock WHERE nom = ?", (f"_TEMP_{category_name}",))
        
        conn.commit()
        logger.info(f"Nouvelle catégorie '{category_name}' ajoutée")
        return True, "Catégorie ajoutée avec succès"
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la catégorie: {e}")
        conn.rollback()
        return False, f"Erreur lors de l'ajout: {str(e)}"
    finally:
        conn.close()

# --- Fonctions pour l'historique et les états des stocks ---
def get_stock_modifications_history():
    """Récupère l'historique complet des modifications de stock"""
    conn = sqlite3.connect(env.get_database_path())
    query = """
        SELECT sm.*, a.nom, a.prenom, s.nom as stock_nom, s.categorie, s.sous_categorie
        FROM StockModifications sm
        JOIN Admins a ON sm.id_user = a.id
        JOIN Stock s ON sm.id_stock = s.id
        ORDER BY sm.date_demande DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_stock_statistics():
    """Récupère les statistiques complètes du stock"""
    conn = sqlite3.connect(env.get_database_path())
    
    # Statistiques générales
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM Stock")
    total_articles = c.fetchone()[0]
    
    c.execute("SELECT SUM(quantite) FROM Stock")
    total_quantite = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM Stock WHERE quantite < seuil_alerte")
    alertes_stock = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM Stock WHERE quantite = 0")
    stock_epuise = c.fetchone()[0]
    
    # Dernières modifications
    c.execute("""
        SELECT sm.date_demande, a.nom, a.prenom, s.nom as stock_nom, s.categorie, sm.status, sm.quantite_demandee
        FROM StockModifications sm
        JOIN Admins a ON sm.id_user = a.id
        JOIN Stock s ON sm.id_stock = s.id
        ORDER BY sm.date_demande DESC
        LIMIT 10
    """)
    dernieres_modifs = c.fetchall()
    
    # Articles par catégorie
    c.execute("""
        SELECT categorie, COUNT(*) as count, SUM(quantite) as total
        FROM Stock
        GROUP BY categorie
        ORDER BY count DESC
    """)
    stats_par_categorie = c.fetchall()
    
    # Sous-catégories de Nourriture
    c.execute("""
        SELECT sous_categorie, COUNT(*) as count, SUM(quantite) as total
        FROM Stock
        WHERE categorie = 'Nourriture' AND sous_categorie IS NOT NULL AND sous_categorie != ''
        GROUP BY sous_categorie
        ORDER BY count DESC
    """)
    stats_nourriture_sous_categories = c.fetchall()
    
    conn.close()
    
    return {
        'total_articles': total_articles,
        'total_quantite': total_quantite,
        'alertes_stock': alertes_stock,
        'stock_epuise': stock_epuise,
        'dernieres_modifs': dernieres_modifs,
        'stats_par_categorie': stats_par_categorie,
        'stats_nourriture_sous_categories': stats_nourriture_sous_categories
    }

def get_recent_stock_changes(days=7):
    """Récupère les changements récents du stock (par défaut 7 jours)"""
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("""
        SELECT s.nom, s.categorie, s.sous_categorie, s.quantite,
               sm.quantite_actuelle, sm.quantite_demandee, sm.date_demande, sm.status,
               a.nom as user_nom, a.prenom as user_prenom
        FROM StockModifications sm
        JOIN Stock s ON sm.id_stock = s.id
        JOIN Admins a ON sm.id_user = a.id
        WHERE sm.date_demande >= datetime('now', '-{} days')
        ORDER BY sm.date_demande DESC
    """.format(days))
    
    changes = c.fetchall()
    conn.close()
    return changes

def get_low_stock_items():
    """Récupère tous les articles en alerte de stock bas"""
    conn = sqlite3.connect(env.get_database_path())
    query = """
        SELECT s.nom, s.categorie, s.sous_categorie, s.quantite, s.seuil_alerte, s.emoji
        FROM Stock s
        WHERE s.quantite < s.seuil_alerte
        ORDER BY s.quantite ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def import_inventory_from_csv(csv_data):
    """
    Importe les articles d'inventaire depuis un fichier CSV.
    Le CSV doit avoir les colonnes: Catégorie, Sous-catégorie, Nom de l'article, Quantité initiale
    """
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    
    try:
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for index, row in csv_data.iterrows():
            try:
                # Nettoyer les données
                categorie = str(row.get('Catégorie', '')).strip()
                sous_categorie = str(row.get('Sous-catégorie', '')).strip()
                nom = str(row.get('Nom de l\'article', '')).strip()
                quantite = int(row.get('Quantité initiale', 0)) if pd.notna(row.get('Quantité initiale')) else 0
                
                # Vérifier que les champs obligatoires sont présents
                if not nom:
                    errors.append(f"Ligne {index + 1}: Nom de l'article manquant")
                    skipped_count += 1
                    continue
                
                if not categorie:
                    errors.append(f"Ligne {index + 1}: Catégorie manquante")
                    skipped_count += 1
                    continue
                
                # Vérifier si l'article existe déjà
                c.execute("SELECT id FROM Stock WHERE nom = ?", (nom,))
                existing = c.fetchone()
                
                if existing:
                    errors.append(f"Ligne {index + 1}: Article '{nom}' existe déjà")
                    skipped_count += 1
                    continue
                
                # Ajouter la sous-catégorie si elle n'existe pas
                if sous_categorie:
                    c.execute("INSERT OR IGNORE INTO SousCategories (nom_categorie, nom_sous_categorie) VALUES (?, ?)", 
                             (categorie, sous_categorie))
                
                # Ajouter l'article avec un emoji par défaut selon la catégorie
                emoji_map = {
                    "Nourriture": "🍔",
                    "Fournitures": "📝", 
                    "Intendance": "🧼",
                    "Bibliothèque": "📚"
                }
                emoji = emoji_map.get(categorie, "📦")
                
                # Insérer l'article
                c.execute("""
                    INSERT INTO Stock (nom, categorie, sous_categorie, quantite, seuil_alerte, emoji) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nom, categorie, sous_categorie, quantite, 5, emoji))
                
                imported_count += 1
                logger.info(f"Article '{nom}' importé avec succès")
                
            except Exception as e:
                errors.append(f"Ligne {index + 1}: Erreur - {str(e)}")
                skipped_count += 1
                continue
        
        conn.commit()
        
        result = {
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors
        }
        
        logger.info(f"Importation CSV terminée: {imported_count} importés, {skipped_count} ignorés")
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'importation CSV: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

# --- Fonctions pour les sous-catégories ---
def get_categories_with_subcategories():
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT nom_categorie, nom_sous_categorie FROM SousCategories ORDER BY nom_categorie, nom_sous_categorie")
    
    categories = {}
    for cat, subcat in c.fetchall():
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(subcat)
        
    conn.close()
    return categories

def add_subcategory(category_name, subcategory_name):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        c.execute("INSERT INTO SousCategories (nom_categorie, nom_sous_categorie) VALUES (?, ?)", (category_name, subcategory_name))
        conn.commit()
        logger.info(f"Nouvelle sous-catégorie '{subcategory_name}' ajoutée à '{category_name}'.")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Tentative d'ajout d'une sous-catégorie existante : '{subcategory_name}' dans '{category_name}'.")
        return False
    finally:
        conn.close()

# --- Fonctions Utilisateurs (Admins) ---
def get_admin_benevoles_emails():
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT email FROM Admins WHERE role IN ('AdminBenevoles', 'Super Admin') AND email IS NOT NULL")
    emails = [row[0] for row in c.fetchall()]
    conn.close()
    return emails

def get_compta_emails():
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT email FROM Admins WHERE role IN ('Compta', 'Super Admin') AND email IS NOT NULL")
    emails = [row[0] for row in c.fetchall()]
    conn.close()
    return emails

def create_pending_admin(username, password, role, nom, prenom, email, telephone):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        c.execute("INSERT INTO Admins (username, password_hash, role, nom, prenom, email, telephone, validation_status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                  (username, hash_password(password), role, nom, prenom, email, telephone))
        conn.commit()
        logger.info(f"Demande de compte en attente créée pour '{username}' (Rôle: {role}).")
        st.success("Votre demande de compte a été envoyée.")
    except sqlite3.IntegrityError:
        logger.warning(f"Tentative de création de compte avec un nom d'utilisateur existant : '{username}'.")
        st.toast(f"❌ Ce nom d'utilisateur existe déjà.", icon='🚨')
    conn.close()

def get_user(username):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT id, password_hash, role, validation_status, nom, prenom FROM Admins WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result

def get_all_users(current_user_id):
    conn = sqlite3.connect(env.get_database_path())
    df = pd.read_sql_query("SELECT id, username, nom, prenom, role FROM Admins WHERE id != ?", conn, params=(current_user_id,))
    conn.close()
    return df

def update_user_role(user_id, new_role):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("UPDATE Admins SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Rôle de l'utilisateur ID {user_id} mis à jour vers '{new_role}'.")

def get_user_profile(user_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT nom, prenom, email, telephone, rib FROM Admins WHERE id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_user_profile(user_id, nom, prenom, email, telephone, rib):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("UPDATE Admins SET nom=?, prenom=?, email=?, telephone=?, rib=? WHERE id=?",
              (nom, prenom, email, telephone, rib, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Profil utilisateur ID {user_id} mis à jour.")

def get_pending_admins():
    conn = sqlite3.connect(env.get_database_path())
    df = pd.read_sql_query("SELECT id, username, role FROM Admins WHERE validation_status = 'pending'", conn)
    conn.close()
    return df

def update_validation_status(admin_id, new_status):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("UPDATE Admins SET validation_status = ? WHERE id = ?", (new_status, admin_id))
    conn.commit()
    conn.close()
    logger.info(f"Statut de validation de l'admin ID {admin_id} mis à jour vers '{new_status}'.")

def delete_admin(admin_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("DELETE FROM Admins WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()
    logger.info(f"Admin ID {admin_id} supprimé.")

# --- Fonctions Notes de Frais ---
def add_expense(user_id, user_full_name, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise, uploaded_files):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("""
        INSERT INTO NotesDeFrais 
        (id_user, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remboursement_deja_emis, remise) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise))
    
    note_id = c.lastrowid

    if uploaded_files:
        for uploaded_file in uploaded_files:
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}_{uploaded_file.name}"
            filepath = os.path.join(UPLOADS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
            c.execute("INSERT INTO FichiersNotesDeFrais (id_note_de_frais, nom_fichier) VALUES (?, ?)", (note_id, filename))
            logger.info(f"Fichier '{filename}' lié à la note de frais ID {note_id}.")

    conn.commit()
    conn.close()
    logger.info(f"Note de frais ID {note_id} ajoutée par l'utilisateur ID {user_id}.")
    
    recipient_emails = get_compta_emails()
    send_new_expense_alert_email(user_full_name, montant, rattachement, recipient_emails)

def get_files_for_expense(expense_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT nom_fichier FROM FichiersNotesDeFrais WHERE id_note_de_frais = ?", (expense_id,))
    results = c.fetchall()
    conn.close()
    return [row[0] for row in results]

def delete_expense(expense_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    
    files_to_delete = get_files_for_expense(expense_id)
    
    for filename in files_to_delete:
        filepath = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Fichier '{filename}' supprimé du système de fichiers.")
            
    c.execute("DELETE FROM FichiersNotesDeFrais WHERE id_note_de_frais = ?", (expense_id,))
    c.execute("DELETE FROM NotesDeFrais WHERE id = ?", (expense_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"Note de frais ID {expense_id} et ses fichiers associés supprimés.")

def update_expense_details(expense_id, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("""
        UPDATE NotesDeFrais SET
        date_depense = ?, rattachement = ?, fournisseur = ?, nature_charge = ?, montant = ?, 
        commentaires = ?, remboursement_deja_emis = ?, remise = ?
        WHERE id = ?
    """, (date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise, expense_id))
    conn.commit()
    conn.close()
    logger.info(f"Note de frais ID {expense_id} mise à jour par l'utilisateur.")

def update_expense_by_accountant(expense_id, new_status, new_comment):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("UPDATE NotesDeFrais SET status = ?, commentaires_compta = ? WHERE id = ?", (new_status, new_comment, expense_id))
    conn.commit()
    conn.close()
    logger.info(f"Note de frais ID {expense_id} mise à jour par la comptabilité (Statut: {new_status}).")

def get_expenses_by_user(user_id):
    conn = sqlite3.connect(env.get_database_path())
    df = pd.read_sql_query("SELECT * FROM NotesDeFrais WHERE id_user = ? ORDER BY date_soumission DESC", conn, params=(user_id,))
    conn.close()
    return df

def get_all_expenses():
    conn = sqlite3.connect(env.get_database_path())
    query = """
    SELECT n.*, a.nom, a.prenom, a.rib
    FROM NotesDeFrais n JOIN Admins a ON n.id_user = a.id
    ORDER BY n.date_soumission DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# --- Fonctions Stock ---
def check_and_send_alert(stock_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT nom, quantite, seuil_alerte, alert_sent FROM Stock WHERE id = ?", (stock_id,))
    item = c.fetchone()
    
    if item:
        nom, quantite, seuil_alerte, alert_sent = item
        if quantite < seuil_alerte and not alert_sent:
            recipient_emails = get_admin_benevoles_emails()
            if recipient_emails:
                send_alert_email(nom, quantite, seuil_alerte, recipient_emails)
                c.execute("UPDATE Stock SET alert_sent = 1 WHERE id = ?", (stock_id,))
                conn.commit()
                logger.warning(f"Alerte de stock bas envoyée pour '{nom}' (Quantité: {quantite}, Seuil: {seuil_alerte}).")
        elif quantite >= seuil_alerte and alert_sent:
            c.execute("UPDATE Stock SET alert_sent = 0 WHERE id = ?", (stock_id,))
            conn.commit()
            logger.info(f"Alerte de stock réinitialisée pour '{nom}' (Quantité: {quantite}, Seuil: {seuil_alerte}).")
            
    conn.close()

def create_stock_modification_request(user_id, stock_id, current_qty, requested_qty):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("INSERT INTO StockModifications (id_user, id_stock, quantite_actuelle, quantite_demandee) VALUES (?, ?, ?, ?)",
              (user_id, stock_id, current_qty, requested_qty))
    conn.commit()
    conn.close()
    logger.info(f"Demande de modification de stock créée par l'utilisateur ID {user_id} pour l'article ID {stock_id} (Quantité: {current_qty} -> {requested_qty}).")

def get_pending_stock_modifications():
    conn = sqlite3.connect(env.get_database_path())
    query = """
    SELECT sm.id, sm.id_stock, sm.date_demande, a.prenom, a.nom as user_nom, s.nom as stock_nom, sm.quantite_actuelle, sm.quantite_demandee
    FROM StockModifications sm
    JOIN Admins a ON sm.id_user = a.id
    JOIN Stock s ON sm.id_stock = s.id
    WHERE sm.status = 'En attente'
    ORDER BY sm.date_demande DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def approve_stock_modification(modif_id, stock_id, new_quantity, approver_id=None):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    
    # Récupérer la quantité actuelle avant modification
    c.execute("SELECT quantite FROM Stock WHERE id = ?", (stock_id,))
    current_qty = c.fetchone()[0]
    
    # Mettre à jour le stock
    c.execute("UPDATE Stock SET quantite = ? WHERE id = ?", (new_quantity, stock_id))
    
    # Si un approver_id est fourni et que la quantité a changé, enregistrer la modification
    if approver_id is not None and current_qty != new_quantity:
        c.execute("""
            INSERT INTO StockModifications (id_user, id_stock, quantite_actuelle, quantite_demandee, status) 
            VALUES (?, ?, ?, ?, 'Approuvée')
        """, (approver_id, stock_id, current_qty, new_quantity))
        logger.info(f"Modification d'approbation enregistrée: Article ID {stock_id}, quantité {current_qty} -> {new_quantity} par approbateur ID {approver_id}")
    
    # Mettre à jour le statut de la modification originale
    c.execute("UPDATE StockModifications SET status = 'Approuvée' WHERE id = ?", (modif_id,))
    
    conn.commit()
    conn.close()
    check_and_send_alert(stock_id)
    logger.info(f"Modification de stock ID {modif_id} approuvée pour l'article ID {stock_id} (Nouvelle quantité: {new_quantity}).")

def refuse_stock_modification(modif_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("UPDATE StockModifications SET status = 'Refusée' WHERE id = ?", (modif_id,))
    conn.commit()
    conn.close()
    logger.info(f"Modification de stock ID {modif_id} refusée.")

def get_stock_item(stock_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("SELECT * FROM Stock WHERE id = ?", (stock_id,))
    result = c.fetchone()
    conn.close()
    return result

def add_item(nom, categorie, sous_categorie, quantite, seuil_alerte, emoji_str):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        emoji_char = emoji_str.split(' ')[0]
        c.execute("INSERT INTO Stock (nom, categorie, sous_categorie, quantite, seuil_alerte, emoji) VALUES (?, ?, ?, ?, ?, ?)",
                  (nom, categorie, sous_categorie, quantite, seuil_alerte, emoji_char))
        conn.commit()
        item_id = c.lastrowid
        check_and_send_alert(item_id)
        logger.info(f"Article '{nom}' (ID: {item_id}) ajouté avec succès dans la sous-catégorie '{sous_categorie}'.")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Tentative d'ajout d'un article avec un nom existant : '{nom}'.")
        st.toast(f"❌ Un article avec le nom '{nom}' existe déjà.", icon='🚨')
        return False
    finally:
        conn.close()

def get_all_items():
    conn = sqlite3.connect(env.get_database_path())
    df = pd.read_sql_query("SELECT * FROM Stock", conn)
    conn.close()
    return df

def update_quantity(item_id, new_qty, user_id=None):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    
    # Récupérer la quantité actuelle avant modification
    c.execute("SELECT quantite FROM Stock WHERE id = ?", (item_id,))
    current_qty = c.fetchone()[0]
    
    # Mettre à jour la quantité
    c.execute("UPDATE Stock SET quantite = ? WHERE id = ?", (new_qty, item_id))
    
    # Si un user_id est fourni, enregistrer la modification dans StockModifications
    if user_id is not None and current_qty != new_qty:
        c.execute("""
            INSERT INTO StockModifications (id_user, id_stock, quantite_actuelle, quantite_demandee, status) 
            VALUES (?, ?, ?, ?, 'Approuvée')
        """, (user_id, item_id, current_qty, new_qty))
        logger.info(f"Modification directe enregistrée: Article ID {item_id}, quantité {current_qty} -> {new_qty} par utilisateur ID {user_id}")
    
    conn.commit()
    conn.close()
    check_and_send_alert(item_id)
    logger.info(f"Quantité de l'article ID {item_id} mise à jour vers {new_qty}.")

def delete_item(item_id):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    c.execute("DELETE FROM Stock WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    logger.info(f"Article ID {item_id} supprimé.")

def update_item_details(item_id, nom, categorie, sous_categorie, quantite, seuil_alerte, emoji_str):
    conn = sqlite3.connect(env.get_database_path())
    c = conn.cursor()
    try:
        emoji_char = emoji_str.split(' ')[0]
        c.execute("UPDATE Stock SET nom = ?, categorie = ?, sous_categorie = ?, quantite = ?, seuil_alerte = ?, emoji = ? WHERE id = ?",
                  (nom, categorie, sous_categorie, quantite, seuil_alerte, emoji_char, item_id))
        conn.commit()
        check_and_send_alert(item_id)
        logger.info(f"Détails de l'article ID {item_id} mis à jour (Nom: '{nom}', Sous-catégorie: '{sous_categorie}').")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Tentative de mise à jour de l'article ID {item_id} avec un nom existant : '{nom}'.")
        st.toast(f"❌ Un article avec le nom '{nom}' existe déjà. La modification a été annulée.", icon='🚨')
        return False
    finally:
        conn.close()
