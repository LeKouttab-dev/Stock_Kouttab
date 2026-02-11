#!/usr/bin/env python3
"""
Version minimale fonctionnelle de Gestion Stock Kouttab
"""

import streamlit as st
import os
import sys
from datetime import datetime

# Configuration
st.set_page_config(
    page_title="Gestion Stock Kouttab",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Variables environnement
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'local')
if ENVIRONMENT == 'production':
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/home/sc9bewu6999/stock.lekouttab.fr/data/stock_kouttab.db')
else:
    DATABASE_PATH = 'data/stock_kouttab.db'

# Base de données simplifiée
import sqlite3

def init_db():
    """Initialisation base de données simplifiée"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Table utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table produits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            price REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Interface principale
def main():
    """Interface principale simplifiée"""
    st.title("🚀 Gestion Stock Kouttab")
    st.success("✅ Application déployée avec succès sur O2Switch !")
    
    st.sidebar.title("Menu")
    page = st.sidebar.selectbox("Choisir une page", [
        "Tableau de bord",
        "Gestion du Stock",
        "Administration"
    ])
    
    if page == "Tableau de bord":
        st.header("📊 Tableau de bord")
        st.info("Tableau de bord - En cours de développement")
        
    elif page == "Gestion du Stock":
        st.header("📦 Gestion du Stock")
        st.info("Gestion du stock - En cours de développement")
        
    elif page == "Administration":
        st.header("⚙️ Administration")
        st.info("Administration - En cours de développement")

# Point d'entrée WSGI
def application(environ, start_response):
    """Point d'entrée WSGI pour O2Switch"""
    try:
        # Initialiser la base de données
        init_db()
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Gestion Stock Kouttab</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=/">
    <style>
        body { font-family: Arial; text-align: center; margin-top: 100px; }
        .success { color: #4CAF50; font-size: 24px; }
    </style>
</head>
<body>
    <div class="success">
        <h1>🚀 Gestion Stock Kouttab</h1>
        <p>Application fonctionnelle !</p>
        <p>Redirection vers l'application...</p>
    </div>
</body>
</html>
        """
        
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(html)))
        ])
        
        return [html.encode('utf-8')]
        
    except Exception as e:
        error_msg = f"Erreur: {str(e)}"
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(error_msg)))
        ])
        return [error_msg.encode('utf-8')]

if __name__ == "__main__":
    main()
