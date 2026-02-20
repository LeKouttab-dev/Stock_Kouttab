#!/usr/bin/env python3
"""
Version de database.py pour MySQL
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
            return sqlite3.connect(DATABASE_PATH)
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {e}")
        st.error(f"Erreur de connexion à la base de données: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn is None:
        return False
    
    c = conn.cursor()
    
    # Création des tables (adapté pour MySQL)
    tables_sql = [
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS Categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom VARCHAR(255) NOT NULL UNIQUE,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # ... autres tables MySQL
    ]
    
    for table_sql in tables_sql:
        c.execute(table_sql)
    
    # Insérer les catégories par défaut
    default_categories = ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"]
    for category in default_categories:
        if 'DATABASE_CONFIG' in globals():
            c.execute("INSERT IGNORE INTO Categories (nom, is_default) VALUES (%s, %s)", (category, True))
        else:
            c.execute("INSERT OR IGNORE INTO Categories (nom, is_default) VALUES (?, ?)", (category, True))
    
    conn.commit()
    conn.close()
    logger.info("Base de données initialisée.")
    return True

# Adapter les autres fonctions pour MySQL...
# (Le reste des fonctions serait adapté similairement)
