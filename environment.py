"""
Configuration multi-environnements pour Gestion Stock Kouttab.

⚠️ IMPORTANT :
- L’ancienne logique basée sur un fichier SQLite (.db) est abandonnée.
- La base de données est désormais une base MySQL distante (O2Switch),
  configurée via st.secrets['db'] dans Streamlit (voir database.get_db_connection()).
- Ce module ne gère plus aucun chemin de fichier de base de données.
"""

import os
from pathlib import Path


class Environment:
    """Classe de gestion des environnements (domaine, logs, email, etc.)."""

    def __init__(self):
        self.env = os.environ.get("ENVIRONMENT", "development").lower()
        self.base_dir = Path(__file__).parent

    # --- Environnement ---

    def is_production(self) -> bool:
        """Vérifie si on est en production."""
        return self.env == "production"

    def is_development(self) -> bool:
        """Vérifie si on est en développement."""
        return self.env == "development"

    # --- BASE DE DONNÉES (DÉPRÉCIÉ) ---

    def get_database_path(self):
        """
        ⚠️ DÉPRÉCIÉ : ne plus utiliser.
        La base est maintenant une base MySQL distante, configurée via st.secrets['db'].
        Cette méthode est conservée uniquement pour compatibilité éventuelle.
        """
        # On renvoie une valeur symbolique pour éviter toute confusion avec un vrai chemin .db
        return "REMOTE_DB_MYSQL_VIA_ST_SECRETS"

    # --- Domaine / URL ---

    def get_domain_url(self) -> str:
        """Retourne l'URL du domaine selon l'environnement."""
        if self.is_production():
            return os.environ.get("DOMAIN_URL", "https://stock.lekouttab.fr")
        return "http://localhost:8501"

    # --- Logs / debug ---

    def get_log_level(self) -> str:
        """Retourne le niveau de log selon l'environnement."""
        return "INFO" if self.is_production() else "DEBUG"

    def get_debug_mode(self) -> bool:
        """Retourne le mode debug selon l'environnement."""
        return not self.is_production()

    # --- Configuration email ---

    def get_email_config(self) -> dict:
        """Retourne la configuration email selon l'environnement."""
        if self.is_production():
            return {
                "smtp_server": os.environ.get("EMAIL_SMTP", "mail.lekouttab.fr"),
                "smtp_port": int(os.environ.get("EMAIL_PORT", "465")),
                "sender_email": os.environ.get("EMAIL_SENDER", "no-reply@lekouttab.fr"),
                "sender_password": os.environ.get("EMAIL_PASSWORD", ""),
                "use_tls": True,
            }
        return {
            "smtp_server": "localhost",
            "smtp_port": 1025,
            "sender_email": "test@localhost",
            "sender_password": "test",
            "use_tls": False,
        }

    # --- Infos debug console ---

    def print_environment_info(self):
        """Affiche les informations de l'environnement actuel."""
        print(f"🌍 ENVIRONNEMENT: {self.env.upper()}")
        print(f"🌐 Domaine URL: {self.get_domain_url()}")
        print(f"📊 Niveau log: {self.get_log_level()}")
        print(f"🐛 Mode debug: {self.get_debug_mode()}")
        print("-" * 50)


# Instance globale de l'environnement
env = Environment()

# Variables globales (compatibilité)
ENVIRONMENT = env.env
DOMAIN_URL = env.get_domain_url()
DEBUG_MODE = env.get_debug_mode()
LOG_LEVEL = env.get_log_level()
EMAIL_CONFIG = env.get_email_config()
# Pas de DATABASE_PATH ici : la base est gérée via st.secrets['db'] et database.get_db_connection()

