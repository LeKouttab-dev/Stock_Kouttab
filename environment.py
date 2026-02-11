"""
Configuration multi-environnements pour Gestion Stock Kouttab
Permet de basculer facilement entre PROD et DEV
"""

import os
from pathlib import Path

class Environment:
    """Classe de gestion des environnements"""
    
    def __init__(self):
        self.env = os.environ.get('ENVIRONMENT', 'development').lower()
        self.base_dir = Path(__file__).parent
        
    def is_production(self):
        """Vérifie si on est en production"""
        return self.env == 'production'
    
    def is_development(self):
        """Vérifie si on est en développement"""
        return self.env == 'development'
    
    def get_database_path(self):
        """Retourne le chemin de la base de données selon l'environnement"""
        if self.is_production():
            return os.environ.get('DATABASE_PATH', 
                '/home/sc9bewu6999/stock.lekouttab.fr/data/stock_kouttab.db')
        else:
            return 'data/stock_kouttab.db'
    
    def get_domain_url(self):
        """Retourne l'URL du domaine selon l'environnement"""
        if self.is_production():
            return os.environ.get('DOMAIN_URL', 'https://stock.lekouttab.fr')
        else:
            return 'http://localhost:8501'
    
    def get_log_level(self):
        """Retourne le niveau de log selon l'environnement"""
        return 'INFO' if self.is_production() else 'DEBUG'
    
    def get_debug_mode(self):
        """Retourne le mode debug selon l'environnement"""
        return not self.is_production()
    
    def get_email_config(self):
        """Retourne la configuration email selon l'environnement"""
        if self.is_production():
            return {
                'smtp_server': os.environ.get('EMAIL_SMTP', 'mail.lekouttab.fr'),
                'smtp_port': int(os.environ.get('EMAIL_PORT', '465')),
                'sender_email': os.environ.get('EMAIL_SENDER', 'no-reply@lekouttab.fr'),
                'sender_password': os.environ.get('EMAIL_PASSWORD', ''),
                'use_tls': True
            }
        else:
            return {
                'smtp_server': 'localhost',
                'smtp_port': 1025,
                'sender_email': 'test@localhost',
                'sender_password': 'test',
                'use_tls': False
            }
    
    def print_environment_info(self):
        """Affiche les informations de l'environnement actuel"""
        print(f"🌍 ENVIRONNEMENT: {self.env.upper()}")
        print(f"📁 Base de données: {self.get_database_path()}")
        print(f"🌐 Domaine URL: {self.get_domain_url()}")
        print(f"📊 Niveau log: {self.get_log_level()}")
        print(f"🐛 Mode debug: {self.get_debug_mode()}")
        print("-" * 50)

# Instance globale de l'environnement
env = Environment()

# Variables globales pour compatibilité
ENVIRONMENT = env.env
DATABASE_PATH = env.get_database_path()
DOMAIN_URL = env.get_domain_url()
DEBUG_MODE = env.get_debug_mode()
LOG_LEVEL = env.get_log_level()
EMAIL_CONFIG = env.get_email_config()
