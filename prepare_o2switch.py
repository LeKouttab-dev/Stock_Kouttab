#!/usr/bin/env python3
"""
Script de préparation pour déploiement O2Switch
Crée un package optimisé pour l'hébergement
"""

import os
import shutil
import zipfile
from datetime import datetime

def prepare_o2switch_deployment():
    """Prépare les fichiers pour déploiement O2Switch"""
    
    print("PREPARATION DEPLOIEMENT O2SWITCH")
    print("=" * 50)
    
    # Fichiers essentiels pour O2Switch
    files_to_deploy = [
        'app.py',                    # Point d'entrée principal
        'database.py',               # Base de données
        'security.py',               # Sécurité
        'security_middleware.py',      # Middleware sécurité
        'admin_setup.py',            # Setup admin
        'invitation_manager.py',       # Gestion invitations
        'init_admin.py',             # Initialisation admin
        'ui_admin.py',               # Interface admin
        'ui_dashboard.py',           # Tableau de bord
        'ui_expenses.py',            # Notes de frais
        'ui_invoices.py',            # Factures
        'ui_stock.py',               # Gestion stock
        'email_utils.py',            # Emails
        'logger_config.py',          # Logs
        'csv_import.py',             # Import CSV
        'requirements.txt',           # Dépendances
        '.htaccess',                # Configuration Apache
        'wsgi.py',                  # Fichier WSGI (optionnel)
        'wsgi_simple.py'           # Alternative WSGI
    ]
    
    # Dossiers à créer
    dirs_to_create = [
        'data',                      # Base de données
        'logs',                      # Logs
        'uploads',                   # Uploads
        '.streamlit'                 # Configuration Streamlit
    ]
    
    # Nom du package
    package_name = f"o2switch_deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    print(f"Creation du package: {package_name}")
    
    with zipfile.ZipFile(package_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Ajouter les fichiers essentiels
        for file in files_to_deploy:
            if os.path.exists(file):
                zipf.write(file, file)
                print(f"Ajoute: {file}")
            else:
                print(f"Manquant: {file}")
        
        # Ajouter les dossiers avec leur .htaccess
        for dir_name in dirs_to_create:
            # Créer le dossier vide dans le ZIP
            zipf.writestr(f"{dir_name}/", "")
            
            # Ajouter .htaccess si existe
            htaccess_path = f"{dir_name}/.htaccess"
            if os.path.exists(htaccess_path):
                zipf.write(htaccess_path, htaccess_path)
                print(f"Ajoute: {htaccess_path}")
        
        # Ajouter configuration Streamlit
        if os.path.exists('.streamlit/secrets.toml'):
            zipf.write('.streamlit/secrets.toml', '.streamlit/secrets.toml.example')
            print("Ajoute: .streamlit/secrets.toml.example")
    
    # Taille du package
    size = os.path.getsize(package_name)
    print(f"\nPackage créé: {package_name}")
    print(f"Taille: {size:,} octets ({size/1024/1024:.1f} MB)")
    
    # Instructions
    print(f"\nINSTRUCTIONS O2SWITCH:")
    print(f"1. Uploadez {package_name} via FTP")
    print(f"2. Décompressez dans /www/stock.lekouttab.fr/")
    print(f"3. Renommez .streamlit/secrets.toml.example en .streamlit/secrets.toml")
    print(f"4. Configurez les variables d'environnement dans O2Switch")
    print(f"5. Installez les dépendances avec pip install -r requirements.txt")
    print(f"6. Démarrez l'application")
    
    return package_name

if __name__ == "__main__":
    prepare_o2switch_deployment()
