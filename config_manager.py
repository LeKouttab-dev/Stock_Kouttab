import streamlit as st
import os
from database import DATABASE_NAME

def load_environment():
    """Charge la configuration selon l'environnement"""
    
    # Détecter l'environnement
    env_mode = os.getenv('APP_MODE', 'local')  # local par défaut
    
    if env_mode == 'production':
        # Configuration production (o2switch)
        config = {
            'base_url': st.secrets.get("app", {}).get("base_url", "https://votredomaine.com"),
            'database_path': 'data/stock_kouttab.db',
            'debug': False
        }
        st.info("🌐 **MODE PRODUCTION** - Configuration o2switch")
        
    else:
        # Configuration locale
        config = {
            'base_url': 'http://localhost:8501',
            'database_path': 'data/stock_kouttab.db', 
            'debug': True
        }
        st.info("🏠 **MODE LOCAL** - Configuration développement")
    
    return config

def get_config():
    """Retourne la configuration actuelle"""
    return load_environment()

# Pour utiliser dans app.py, remplacez les lignes de configuration
# par des appels à get_config()
