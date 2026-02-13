# Configuration pour l'environnement de PRODUCTION
# À utiliser sur O2Switch uniquement

# Type d'environnement
ENVIRONMENT=production

# Base de données sur O2Switch
DATABASE_PATH=/www/stock.lekouttab.fr/data/stock_kouttab.db

# URL de production
DOMAIN_URL=https://stock.lekouttab.fr

# Mode debug désactivé en production
DEBUG_MODE=false

# Niveau de log minimal en production
LOG_LEVEL=INFO

# Configuration email pour production
EMAIL_SMTP=mail.lekouttab.fr
EMAIL_PORT=465
EMAIL_SENDER=no-reply@lekouttab.fr
EMAIL_PASSWORD=***REMOVED***

# Clé secrète sécurisée pour production
SECRET_KEY=***REMOVED***

# Configuration Streamlit pour production
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLE_CORS=false
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true

# Sécurité
ALLOWED_HOSTS=stock.lekouttab.fr,www.stock.lekouttab.fr
