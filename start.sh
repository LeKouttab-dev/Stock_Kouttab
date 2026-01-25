#!/bin/bash
# Script de démarrage pour Gestion Le Kouttâb (Linux/macOS)

echo "🚀 Démarrage de Gestion Le Kouttâb..."
echo

# Vérifier si les dépendances sont installées
python3 -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Streamlit n'est pas installé"
    echo "Veuillez d'abord exécuter: ./install.sh"
    exit 1
fi

# Vérifier si la base de données existe
if [ ! -f "data/stock_kouttab.db" ]; then
    echo "⚠️  La base de données n'existe pas"
    echo "Lancement de l'initialisation..."
    python3 -c "from database import init_db; init_db()"
fi

# Vérifier si un admin existe
ADMIN_COUNT=$(python3 -c "
import sqlite3
conn = sqlite3.connect('data/stock_kouttab.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM Admins WHERE role=\"Super Admin\"')
count = c.fetchone()[0]
conn.close()
print(count)
")

if [ "$ADMIN_COUNT" -eq 0 ]; then
    echo
    echo "👑 Aucun administrateur trouvé!"
    echo
    echo "Options:"
    echo "1. Ouvrir la page d'initialisation: http://localhost:8501?init_admin=true"
    echo "2. Annuler"
    echo
    read -p "Votre choix (1/2): " choice
    
    if [ "$choice" = "1" ]; then
        echo "🌐 Démarrage avec page d'initialisation..."
        if command -v xdg-open > /dev/null; then
            xdg-open "http://localhost:8501?init_admin=true"
        elif command -v open > /dev/null; then
            open "http://localhost:8501?init_admin=true"
        fi
        streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    else
        echo "Installation annulée."
        exit 0
    fi
else
    echo "✅ Administration configurée"
    echo "🌐 Lancement de l'application..."
    echo
    echo "L'application sera accessible à: http://localhost:8501"
    echo
    streamlit run app.py --server.port=8501 --server.address=0.0.0.0
fi
