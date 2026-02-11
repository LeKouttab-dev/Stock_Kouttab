#!/usr/bin/env python3
# Fichier WSGI simplifié pour O2Switch
# Point d'entrée pour l'application Gestion Stock Kouttab

import os
import sys
from pathlib import Path

# Ajouter le répertoire de l'application au PYTHONPATH
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def application(environ, start_response):
    """
    Point d'entrée WSGI pour O2Switch
    """
    def start_response(status, headers):
        start_response(status, headers)
        return []

    # Page HTML qui redirige automatiquement vers Streamlit
    if environ.get('REQUEST_METHOD') == 'GET':
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        return [b'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
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
        .container {
            text-align: center;
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        .icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
        h1 {
            margin: 0 0 20px 0;
            font-size: 28px;
            font-weight: 300;
        }
        .subtitle {
            font-size: 18px;
            opacity: 0.8;
            margin-bottom: 30px;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .button {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            padding: 12px 24px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            text-decoration: none;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        .button:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">📦</div>
        <h1>Gestion Stock Kouttab</h1>
        <div class="subtitle">
            <span class="loading"></span>
            Redirection vers l'application...
        </div>
        <a href="/" class="button">Accéder directement à l'application</a>
    </div>
</body>
</html>
        ''']
    
    # Pour toute autre requête, rediriger vers la racine
    return start_response('302 Found', [('Location', '/')])

# Point d'entrée WSGI
application = application
