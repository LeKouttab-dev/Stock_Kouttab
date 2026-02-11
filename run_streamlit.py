#!/usr/bin/env python3
"""
Point d'entrée pour O2Switch - Lance Streamlit correctement
"""

import os
import sys
import subprocess
from pathlib import Path

# Configuration
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Variables environnement
os.environ.setdefault('ENVIRONMENT', 'production')

def main():
    """Point d'entrée principal pour O2Switch"""
    try:
        # Lancer Streamlit avec les bonnes options
        cmd = [
            'streamlit', 'run', 'app.py',
            '--server.port=8501',
            '--server.address=0.0.0.0',
            '--server.headless=true',
            '--browser.gatherUsageStats=false',
            '--global.developmentMode=false'
        ]
        
        # Exécuter Streamlit
        process = subprocess.Popen(
            cmd,
            cwd=current_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Attendre que le processus se termine
        stdout, stderr = process.communicate()
        
        # Si erreur, l'afficher
        if process.returncode != 0:
            print(f"Erreur Streamlit: {stderr}")
            return 1
            
        return 0
        
    except Exception as e:
        print(f"Erreur: {e}")
        return 1

# Point d'entrée WSGI pour Passenger
def application(environ, start_response):
    """Point d'entrée WSGI"""
    try:
        # Page de chargement simple
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Gestion Stock Kouttab</title>
    <meta http-equiv="refresh" content="3; url=/">
    <style>
        body { font-family: Arial; text-align: center; margin-top: 100px; }
        .loader { color: #667eea; font-size: 18px; }
    </style>
</head>
<body>
    <div class="loader">
        <h2>🚀 Gestion Stock Kouttab</h2>
        <p>Démarrage en cours...</p>
        <p>Redirection automatique...</p>
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
    sys.exit(main())
