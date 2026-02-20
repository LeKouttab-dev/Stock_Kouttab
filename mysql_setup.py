#!/usr/bin/env python3
"""
Script pour créer la structure MySQL sur O2Switch
"""

import mysql.connector
import streamlit as st
from logger_config import logger

def create_mysql_tables():
    """Crée les tables MySQL si elles n'existent pas"""
    
    try:
        # Connexion à MySQL
        conn = mysql.connector.connect(
            host=st.secrets["connections"]["mysql"]["host"],
            port=st.secrets["connections"]["mysql"]["port"],
            user=st.secrets["connections"]["mysql"]["user"],
            password=st.secrets["connections"]["mysql"]["password"],
            database=st.secrets["connections"]["mysql"]["database"]
        )
        
        cursor = conn.cursor()
        
        # Création des tables
        tables = [
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
            """
            CREATE TABLE IF NOT EXISTS SousCategories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_categorie VARCHAR(255) NOT NULL,
                nom_sous_categorie VARCHAR(255) NOT NULL,
                UNIQUE KEY unique_category_sub (nom_categorie, nom_sous_categorie),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                validation_status VARCHAR(20) DEFAULT 'pending',
                nom VARCHAR(255),
                prenom VARCHAR(255),
                email VARCHAR(255),
                telephone VARCHAR(50),
                rib VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS NotesDeFrais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_user INT NOT NULL,
                date_depense DATE NOT NULL,
                rattachement VARCHAR(255),
                fournisseur VARCHAR(255),
                nature_charge VARCHAR(255),
                montant DECIMAL(10,2) NOT NULL,
                commentaires TEXT,
                remb_emis BOOLEAN DEFAULT FALSE,
                remise DECIMAL(10,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'En attente',
                commentaires_compta TEXT,
                date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_user) REFERENCES Admins(id)
            )
            """,
            """
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
            """,
            """
            CREATE TABLE IF NOT EXISTS Factures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_user INT NOT NULL,
                commentaire TEXT,
                date_depot DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'En attente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (id_user) REFERENCES Admins(id)
            )
            """,
            """
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
            """,
            """
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
                FOREIGN KEY (id_user) REFERENCES Admins(id),
                FOREIGN KEY (id_stock) REFERENCES Stock(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS AdminInvitations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                attempts INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        # Exécuter la création des tables
        for table_sql in tables:
            cursor.execute(table_sql)
        
        # Insérer les catégories par défaut
        default_categories = ["Nourriture", "Fournitures", "Intendance", "Bibliothèque"]
        for category in default_categories:
            cursor.execute("INSERT IGNORE INTO Categories (nom, is_default) VALUES (%s, %s)", (category, True))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.success("✅ Base de données MySQL créée avec succès !")
        logger.info("Structure MySQL créée sur O2Switch")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la création des tables MySQL: {e}")
        logger.error(f"Erreur MySQL: {e}")
        return False

def test_mysql_connection():
    """Test la connexion MySQL"""
    
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            port=st.secrets["mysql"]["port"]
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        conn.close()
        
        st.success(f"✅ Connexion MySQL réussie ! Version: {version[0]}")
        return True
        
    except Exception as e:
        st.error(f"❌ Erreur de connexion MySQL: {e}")
        return False

if __name__ == "__main__":
    st.title("🗄️ Configuration MySQL O2Switch")
    
    if st.button("🔍 Tester la connexion MySQL"):
        test_mysql_connection()
    
    if st.button("🚀 Créer les tables MySQL"):
        create_mysql_tables()
