#!/bin/bash
# Script de déploiement pour stock.lekouttab.fr sur O2Switch

echo "🚀 Déploiement de Gestion Stock Kouttab sur stock.lekouttab.fr"

# Configuration
DOMAIN="stock.lekouttab.fr"
REMOTE_PATH="/www/stock.lekouttab.fr"
LOCAL_PATH="./"

# Vérifier si on est en production
if [ "$1" = "production" ]; then
    echo "📦 Mode production activé"
    
    # Créer les répertoires nécessaires
    mkdir -p data
    mkdir -p logs
    
    # Copier la configuration de production
    cp env.production .env
    
    echo "✅ Configuration production copiée"
    echo "📁 Répertoires créés : data/, logs/"
fi

# Upload des fichiers (à faire manuellement via FileZilla ou interface O2Switch)
echo "📤 Veuillez uploader les fichiers vers :"
echo "   Serveur : O2Switch FTP"
echo "   Chemin : $REMOTE_PATH"
echo "   URL : https://$DOMAIN"

echo ""
echo "📋 Fichiers à uploader :"
echo "   - app.py (principal)"
echo "   - Tous les fichiers .py"
echo "   - requirements.txt"
echo "   - .htaccess"
echo "   - .streamlit/config.toml"

echo ""
echo "🔧 Configuration O2Switch Set Up Applications :"
echo "   Application Root: /www/stock.lekouttab.fr/"
echo "   Domaine: stock.lekouttab.fr"
echo "   Fichier de démarrage: app.py"
echo "   Version Python: 3.11"

echo ""
echo "✅ Après déploiement, vérifiez : https://$DOMAIN"
