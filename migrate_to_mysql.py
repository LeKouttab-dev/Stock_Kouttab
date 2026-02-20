#!/usr/bin/env python3
"""
Script de migration de SQLite vers MySQL
"""

import sqlite3
import mysql.connector
import pandas as pd
import streamlit as st
from logger_config import logger

def migrate_sqlite_to_mysql():
    """Migration des données de SQLite vers MySQL"""
    
    try:
        # Connexion SQLite
        sqlite_conn = sqlite3.connect('data/stock_kouttab.db')
        
        # Connexion MySQL
        mysql_conn = mysql.connector.connect(
            host=st.secrets["connections"]["mysql"]["host"],
            port=st.secrets["connections"]["mysql"]["port"],
            user=st.secrets["connections"]["mysql"]["user"],
            password=st.secrets["connections"]["mysql"]["password"],
            database=st.secrets["connections"]["mysql"]["database"]
        )
        
        mysql_cursor = mysql_conn.cursor()
        
        st.info("🔄 Migration des données en cours...")
        
        # Migration des catégories
        st.write("📂 Migration des catégories...")
        categories_df = pd.read_sql_query("SELECT * FROM Categories", sqlite_conn)
        for _, row in categories_df.iterrows():
            mysql_cursor.execute("""
                INSERT IGNORE INTO Categories (nom, is_default, created_at) 
                VALUES (%s, %s, %s)
            """, (row['nom'], row['is_default'], row.get('created_at', pd.Timestamp.now())))
        
        # Migration des sous-catégories
        st.write("📂 Migration des sous-catégories...")
        subcategories_df = pd.read_sql_query("SELECT * FROM SousCategories", sqlite_conn)
        for _, row in subcategories_df.iterrows():
            mysql_cursor.execute("""
                INSERT IGNORE INTO SousCategories (nom_categorie, nom_sous_categorie, created_at) 
                VALUES (%s, %s, %s)
            """, (row['nom_categorie'], row['nom_sous_categorie'], row.get('created_at', pd.Timestamp.now())))
        
        # Migration du stock
        st.write("📦 Migration des articles en stock...")
        stock_df = pd.read_sql_query("SELECT * FROM Stock", sqlite_conn)
        for _, row in stock_df.iterrows():
            mysql_cursor.execute("""
                INSERT INTO Stock (nom, categorie, sous_categorie, quantite, seuil_alerte, emoji, alert_sent, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['nom'], row['categorie'], row['sous_categorie'], 
                row['quantite'], row['seuil_alerte'], row['emoji'], row['alert_sent'],
                row.get('created_at', pd.Timestamp.now()), row.get('updated_at', pd.Timestamp.now())
            ))
        
        # Migration des administrateurs
        st.write("👑 Migration des administrateurs...")
        admins_df = pd.read_sql_query("SELECT * FROM Admins", sqlite_conn)
        for _, row in admins_df.iterrows():
            mysql_cursor.execute("""
                INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email, telephone, rib, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['username'], row['password_hash'], row['role'], row['validation_status'],
                row['nom'], row['prenom'], row['email'], row['telephone'], row['rib'],
                row.get('created_at', pd.Timestamp.now()), row.get('updated_at', pd.Timestamp.now())
            ))
        
        mysql_conn.commit()
        mysql_cursor.close()
        mysql_conn.close()
        sqlite_conn.close()
        
        st.success("✅ Migration terminée avec succès !")
        logger.info("Migration SQLite vers MySQL terminée")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la migration: {e}")
        logger.error(f"Erreur migration: {e}")
        return False

if __name__ == "__main__":
    st.title("🗄️ Migration SQLite → MySQL")
    
    st.warning("""
    ⚠️ **AVERTISSEMENT IMPORTANT**
    
    Cette opération va migrer TOUTES vos données de SQLite vers MySQL.
    
    - Vérifiez que MySQL est bien configuré
    - Faites une sauvegarde avant
    - L'opération est irréversible
    """)
    
    if st.button("🚀 Lancer la migration", type="primary"):
        with st.spinner("Migration en cours..."):
            migrate_sqlite_to_mysql()
