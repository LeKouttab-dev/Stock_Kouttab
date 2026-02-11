#!/usr/bin/env python3
"""
Version ultra-simple pour tester O2Switch
"""

import os
import sys

def application(environ, start_response):
    """Point d'entrée WSGI simple"""
    try:
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Gestion Stock Kouttab - Test</title>
    <meta charset="utf-8">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            margin-top: 100px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container { 
            max-width: 600px; 
            margin: 0 auto; 
            padding: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        h1 { font-size: 2.5em; margin-bottom: 20px; }
        p { font-size: 1.2em; line-height: 1.6; }
        .status { color: #4CAF50; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Gestion Stock Kouttab</h1>
        <p class="status">✅ Application Python fonctionne !</p>
        <p>L'application est correctement déployée sur O2Switch.</p>
        <p>Configuration en cours pour Streamlit...</p>
        <hr>
        <p><small>Python Version: {}</small></p>
        <p><small>Environment: {}</small></p>
        <p><small>Application Root: {}</small></p>
    </div>
</body>
</html>
        """.format(
            sys.version,
            os.environ.get('ENVIRONMENT', 'Non défini'),
            os.getcwd()
        )
        
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(html_content)))
        ])
        
        return [html_content.encode('utf-8')]
        
    except Exception as e:
        error_msg = f"Erreur: {str(e)}"
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(error_msg)))
        ])
        return [error_msg.encode('utf-8')]

if __name__ == "__main__":
    print("Test application - fonctionne en ligne de commande")
    print("Python version:", sys.version)
    print("Environment:", os.environ.get('ENVIRONMENT', 'Non défini'))
    print("Working directory:", os.getcwd())
