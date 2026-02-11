#!/bin/bash
# Script de démarrage pour Streamlit sur O2Switch

cd /home/sc9bewu6999/stock.lekouttab.fr
source /home/sc9bewu6999/virtualenv/stock.lekouttab.fr/3.11/bin/activate

export ENVIRONMENT=production
export DATABASE_PATH=/home/sc9bewu6999/stock.lekouttab.fr/data/stock_kouttab.db

exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
