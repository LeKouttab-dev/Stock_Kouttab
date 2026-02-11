#!/usr/bin/env python3
"""
Point d'entrée pour O2Switch Passenger
Lance Streamlit correctement pour l'application Gestion Stock Kouttab
"""

import os
import sys
import subprocess
from pathlib import Path

# Ajouter le répertoire courant au PYTHONPATH
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configuration pour O2Switch
os.environ.setdefault('ENVIRONMENT', 'production')

def application(environ, start_response):
    """
    Point d'entrée WSGI qui lance Streamlit
    """
    try:
        # Configuration Streamlit pour O2Switch
        streamlit_cmd = [
            'streamlit', 'run', 'app.py',
            '--server.port=8501',
            '--server.address=0.0.0.0',
            '--server.headless=true',
            '--server.enableCORS=false',
            '--server.enableXSRFProtection=true',
            '--browser.gatherUsageStats=false',
            '--global.developmentMode=false'
        ]
        
        # Lancer Streamlit en subprocess
        process = subprocess.Popen(
            streamlit_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=current_dir
        )
        
        # Attendre un peu que Streamlit démarre
        import time
        time.sleep(2)
        
        # Retourner une page de chargement
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Gestion Stock Kouttab</title>
    <meta http-equiv="refresh" content="2; url=/">
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
        <div class="text">🚀 Démarrage de Gestion Stock Kouttab...</div>
        <div class="text">Redirection automatique...</div>
    </div>
</body>
</html>
        """
        
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(html_content)))
        ])
        
        return [html_content.encode('utf-8')]
        
    except Exception as e:
        # En cas d'erreur
        error_msg = f"Erreur de démarrage: {str(e)}"
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(error_msg)))
        ])
        return [error_msg.encode('utf-8')]

# Point d'entrée principal
if __name__ == "__main__":
    # Si lancé directement, démarrer Streamlit
    import subprocess
    subprocess.run([
        'streamlit', 'run', 'app.py',
        '--server.port=8501',
        '--server.address=0.0.0.0'
    ])
