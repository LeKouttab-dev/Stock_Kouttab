#!/usr/bin/env python3
# Fichier WSGI pour Streamlit sur O2Switch
# Point d'entrée pour l'application Gestion Stock Kouttab

import os
import sys
import subprocess
from pathlib import Path

# Ajouter le répertoire de l'application au PYTHONPATH
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configuration pour O2Switch
os.environ.setdefault('ENVIRONMENT', 'production')

def application(environ, start_response):
    """
    Point d'entrée WSGI pour Streamlit sur O2Switch
    """
    # Importer l'application Streamlit
    from app import main as streamlit_app
    
    # Configurer les variables d'environnement
    os.environ.update(environ)
    
    # Démarrer Streamlit en mode headless
    try:
        # Streamlit n'a pas de vrai support WSGI natif,
        # donc on utilise subprocess pour le démarrer
        import streamlit.web.cli as stcli
        
        # Simuler les arguments de ligne de commande pour Streamlit
        sys.argv = [
            'streamlit',
            'run',
            'app.py',
            '--server.port=8501',
            '--server.address=0.0.0.0',
            '--server.headless=true',
            '--server.enableCORS=false',
            '--server.enableXSRFProtection=true'
        ]
        
        # Démarrer l'application
        return stcli.main()
        
    except Exception as e:
        # En cas d'erreur, retourner une réponse d'erreur
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f"Erreur de démarrage de l'application: {str(e)}".encode('utf-8')]

# Alternative plus simple pour O2Switch
def simple_application(environ, start_response):
    """
    Point d'entrée WSGI simplifié pour O2Switch
    """
    # Pour O2Switch, on peut aussi utiliser une approche plus simple
    # qui consiste à créer un petit serveur web qui redirige vers Streamlit
    
    def start_response(status, headers):
        start_response(status, headers)
        return []

    if environ.get('REQUEST_METHOD') == 'GET':
        # Page de redirection/chargement
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        return [b'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gestion Stock Kouttab</title>
    <meta http-equiv="refresh" content="0; url=/">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .loader {
            text-align: center;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .text {
            margin-top: 20px;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="loader">
        <div class="spinner"></div>
        <div class="text">Démarrage de l'application Gestion Stock Kouttab...</div>
    </div>
</body>
</html>
        ''']
    
    # Pour les autres requêtes, rediriger vers Streamlit
    return start_response('302 Found', [('Location', '/')])

# Point d'entrée principal
application = simple_application
