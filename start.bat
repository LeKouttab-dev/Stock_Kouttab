
@echo off
REM Script de démarrage pour Gestion Le Kouttâb (Windows)

echo 🚀 Démarrage de Gestion Le Kouttâb...
echo.

REM Vérifier si les dépendances sont installées
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo ❌ Streamlit n'est pas installé
    echo Veuillez d'abord exécuter install.bat
    pause
    exit /b 1
)

REM Vérifier si la base de données existe
if not exist "data\stock_kouttab.db" (
    echo ⚠️  La base de données n'existe pas
    echo Lancement de l'initialisation...
    python -c "from database import init_db; init_db()"
)

REM Vérifier si un admin existe
python -c "import sqlite3; conn=sqlite3.connect('data/stock_kouttab.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM Admins WHERE role=\"Super Admin\"'); count=c.fetchone()[0]; conn.close(); exit(0 if count>0 else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo 👑 Aucun administrateur trouvé!
    echo.
    echo Options:
    echo 1. Ouvrir la page d'initialisation: http://localhost:8501?init_admin=true
    echo 2. Annuler
    echo.
    set /p choice="Votre choix (1/2): "
    
    if /i "%choice%"=="1" (
        echo 🌐 Démarrage avec page d'initialisation...
        start http://localhost:8501?init_admin=true
        streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    ) else (
        echo Installation annulée.
        pause
        exit /b 0
    )
) else (
    echo ✅ Administration configurée
    echo 🌐 Lancement de l'application...
    echo.
    echo L'application sera accessible à: http://localhost:8501
    echo.
    streamlit run app.py --server.port=8501 --server.address=0.0.0.0
)

pause
