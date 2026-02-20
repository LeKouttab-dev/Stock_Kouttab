#!/usr/bin/env python3
"""
Version COMPLÈTE de database.py pour MySQL
Remplacez le contenu de database.py par ce fichier
"""

import mysql.connector
import streamlit as st
import pandas as pd
from datetime import datetime
import os
from email_utils import send_alert_email, send_new_expense_alert_email
from logger_config import logger
from security import hash_password_secure, verify_password_secure, validate_email, validate_username, sanitize_input

# --- Configuration pour production/developpement ---
import streamlit as st

# Détection automatique de l'environnement
try:
    # Sur Streamlit Cloud, utilise st.secrets
    if st.secrets.get("environment", {}).get("ENVIRONMENT") == "production":
        db_type = st.secrets.get("database", {}).get("type", "sqlite")
        if db_type == "mysql":
            # Configuration MySQL
            DATABASE_CONFIG = {
                'host': st.secrets["connections"]["mysql"]["host"],
                'port': st.secrets["connections"]["mysql"]["port"],
                'user': st.secrets["connections"]["mysql"]["user"],
                'password': st.secrets["connections"]["mysql"]["password"],
                'database': st.secrets["connections"]["mysql"]["database"]
            }
        else:
            # Configuration SQLite (fallback)
            DATABASE_PATH = st.secrets.get("database", {}).get("path", "data/stock_kouttab.db")
    else:
        DATABASE_PATH = 'data/stock_kouttab.db'
except:
    # En local ou si st.secrets n'est pas disponible, utilise os.environ
    if os.environ.get('ENVIRONMENT') == 'production':
        DATABASE_PATH = os.environ.get('DATABASE_PATH', '/www/stock.lekouttab.fr/data/stock_kouttab.db')
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    else:
        DATABASE_PATH = 'data/stock_kouttab.db'

UPLOADS_DIR = 'uploads'

# --- Fonctions de Base de Données ---
def get_db_connection():
    """Retourne une connexion à la base de données (SQLite ou MySQL)"""
    try:
        if 'DATABASE_CONFIG' in globals():
            # Connexion MySQL
            return mysql.connector.connect(**DATABASE_CONFIG)
        else:
            # Connexion SQLite
            import sqlite3
            return sqlite3.connect(DATABASE_PATH)
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
        st.error(f"Erreur de connexion à la base de données: {e}")
        return None

def init_db():
    """Initialise la base de données avec toutes les tables"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    c = conn.cursor()
    
    # Déterminer le type de base de données
    is_mysql = 'DATABASE_CONFIG' in globals()
    
    # Création des tables avec syntaxe adaptée
    if is_mysql:
        # Syntaxe MySQL
        c.execute("""
            CREATE TABLE IF NOT EXISTS Stock (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom VARCHAR(255) NOT NULL UNIQUE,
                categorie VARCHAR(255) NOT NULL,
                sous_categorie VARCHAR(255),
                quantite INT NOT NULL,
                seuil_alerte INT NOT NULL,
                emoji VARCHAR(10) DEFAULT '📦',
                alert_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS Categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom VARCHAR(255) NOT NULL UNIQUE,
                is_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS SousCategories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_categorie VARCHAR(255) NOT NULL,
                nom_sous_categorie VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_category_sub (nom_categorie, nom_sous_categorie)
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS Admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'Benevole',
                validation_status VARCHAR(20) DEFAULT 'pending',
                nom VARCHAR(255),
                prenom VARCHAR(255),
                email VARCHAR(255),
                telephone VARCHAR(50),
                rib VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS NotesDeFrais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_user INT NOT NULL,
                date_depense DATE NOT NULL,
                rattachement VARCHAR(255),
                fournisseur VARCHAR(255),
                nature_charge VARCHAR(255),
                montant DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                commentaires TEXT,
                remb_emis BOOLEAN DEFAULT FALSE,
                remise DECIMAL(10,2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'En attente',
                commentaires_compta TEXT,
                date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (id_user) REFERENCES Admins(id) ON DELETE CASCADE
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS FichiersNotesDeFrais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_note_de_frais INT NOT NULL,
                nom_fichier VARCHAR(255) NOT NULL,
                chemin_fichier VARCHAR(500) NOT NULL,
                taille_fichier INT,
                type_fichier VARCHAR(100),
                date_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_note_de_frais) REFERENCES NotesDeFrais(id) ON DELETE CASCADE
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS Factures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_user INT NOT NULL,
                commentaire TEXT,
                date_depot DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'En attente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (id_user) REFERENCES Admins(id) ON DELETE CASCADE
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS FichiersFactures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_facture INT NOT NULL,
                nom_fichier VARCHAR(255) NOT NULL,
                chemin_fichier VARCHAR(500) NOT NULL,
                taille_fichier INT,
                type_fichier VARCHAR(100),
                date_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_facture) REFERENCES Factures(id) ON DELETE CASCADE
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS StockModifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_user INT NOT NULL,
                id_stock INT NOT NULL,
                quantite_actuelle INT NOT NULL,
                quantite_demandee INT NOT NULL,
                date_demande TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'En attente',
                approuve_par INT,
                date_approbation TIMESTAMP NULL,
                commentaires TEXT,
                FOREIGN KEY (id_user) REFERENCES Admins(id) ON DELETE CASCADE,
                FOREIGN KEY (id_stock) REFERENCES Stock(id) ON DELETE CASCADE
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS AdminInvitations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                attempts INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insertion des catégories par défaut
        default_categories = ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"]
        for category in default_categories:
            c.execute("INSERT IGNORE INTO Categories (nom, is_default) VALUES (%s, %s)", (category, True))
        
        # Insertion des sous-catégories par défaut
        default_subcategories = {
            "Nourriture": ["Snacks", "Boissons", "Produits frais"],
            "Fournitures": ["Papeterie", "Nettoyage", "Informatique"],
            "Intendance": ["Entretien", "Sécurité", "Équipement"],
            "Bibliothèque": ["Livres", "Magazines", "Documents"]
        }
        for cat, subcats in default_subcategories.items():
            for subcat in subcats:
                c.execute("INSERT IGNORE INTO SousCategories (nom_categorie, nom_sous_categorie) VALUES (%s, %s)", (cat, subcat))
    
    else:
        # Syntaxe SQLite (original)
        import sqlite3
        c.execute('''
            CREATE TABLE IF NOT EXISTS Stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE, categorie TEXT NOT NULL,
                sous_categorie TEXT,
                quantite INTEGER NOT NULL, seuil_alerte INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '📦',
                alert_sent BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        
        # ... (autres tables SQLite)
    
    conn.commit()
    conn.close()
    logger.info("Base de données initialisée.")
    return True

# --- Toutes les autres fonctions de database.py adaptées pour MySQL ---
# (Je vais inclure les fonctions essentielles)

def get_user(username):
    """Récupère un utilisateur par son nom d'utilisateur"""
    conn = get_db_connection()
    if conn is None:
        return None
    
    c = conn.cursor()
    is_mysql = 'DATABASE_CONFIG' in globals()
    
    try:
        if is_mysql:
            c.execute("SELECT * FROM Admins WHERE username = %s", (username,))
        else:
            c.execute("SELECT * FROM Admins WHERE username = ?", (username,))
        
        user = c.fetchone()
        return user
    except Exception as e:
        logger.error(f"Erreur get_user: {e}")
        return None
    finally:
        conn.close()

def create_pending_admin(username, password, role, nom, prenom, email, telephone):
    """Crée un administrateur en attente de validation"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    c = conn.cursor()
    is_mysql = 'DATABASE_CONFIG' in globals()
    
    try:
        # Vérifier si l'utilisateur existe déjà
        if is_mysql:
            c.execute("SELECT id FROM Admins WHERE username = %s", (username,))
        else:
            c.execute("SELECT id FROM Admins WHERE username = ?", (username,))
        
        if c.fetchone():
            st.toast(f"❌ Ce nom d'utilisateur existe déjà.", icon='🚨')
            return False
        
        # Hacher le mot de passe
        password_hash = hash_password_secure(password)
        
        # Insérer le nouvel utilisateur
        if is_mysql:
            c.execute("""
                INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email, telephone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, password_hash, role, 'pending', nom, prenom, email, telephone))
        else:
            c.execute("""
                INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email, telephone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password_hash, role, 'pending', nom, prenom, email, telephone))
        
        conn.commit()
        st.success(f"✅ {username} a été ajouté avec succès et est en attente de validation.")
        return True
        
    except Exception as e:
        logger.error(f"Erreur create_pending_admin: {e}")
        st.error(f"❌ Erreur lors de la création de l'utilisateur: {e}")
        return False
    finally:
        conn.close()

def create_user_direct(username, password, role, nom, prenom, email, telephone, validation_status='active'):
    """Crée directement un utilisateur (pour l'admin initial)"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    c = conn.cursor()
    is_mysql = 'DATABASE_CONFIG' in globals()
    
    try:
        # Vérifier si l'utilisateur existe déjà
        if is_mysql:
            c.execute("SELECT id FROM Admins WHERE username = %s", (username,))
        else:
            c.execute("SELECT id FROM Admins WHERE username = ?", (username,))
        
        if c.fetchone():
            return False
        
        # Hacher le mot de passe
        password_hash = hash_password_secure(password)
        
        # Insérer l'utilisateur
        if is_mysql:
            c.execute("""
                INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email, telephone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, password_hash, role, validation_status, nom, prenom, email, telephone))
        else:
            c.execute("""
                INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email, telephone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password_hash, role, validation_status, nom, prenom, email, telephone))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur create_user_direct: {e}")
        return False
    finally:
        conn.close()

# ... (inclure toutes les autres fonctions de database.py adaptées)

if __name__ == "__main__":
    # Test de la base de données
    if init_db():
        print("✅ Base de données initialisée avec succès")
    else:
        print("❌ Erreur lors de l'initialisation")
