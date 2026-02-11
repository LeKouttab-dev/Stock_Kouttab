# Configuration Multi-Environnements

Ce projet supporte maintenant deux environnements distincts :

## 🌍 Environnements Disponibles

### 🏠 Développement (Development)
- **URL** : http://localhost:8501
- **Base de données** : `data/stock_kouttab.db` (locale)
- **Debug** : Activé
- **Logs** : Niveau DEBUG
- **Email** : Simulation locale

### 🚀 Production (Production)
- **URL** : https://stock.lekouttab.fr
- **Base de données** : `/home/sc9bewu6999/stock.lekouttab.fr/data/stock_kouttab.db`
- **Debug** : Désactivé
- **Logs** : Niveau INFO
- **Email** : Configuration réelle

## 🔧 Utilisation

### Méthode 1 - Scripts de basculement

#### Windows :
```cmd
switch_env.bat development
switch_env.bat production
```

#### Linux/Mac :
```bash
chmod +x switch_env.sh
./switch_env.sh development
./switch_env.sh production
```

### Méthode 2 - Manuel

1. **Développement** :
   ```bash
   cp .env.development .env
   ```

2. **Production** :
   ```bash
   cp .env.production .env
   ```

## 📁 Fichiers de Configuration

- `.env.development` - Configuration développement
- `.env.production` - Configuration production
- `.env` - Configuration active (généré par basculement)
- `environment.py` - Gestionnaire d'environnement

## 🚀 Déploiement

### Pour le déploiement sur O2Switch :
1. Basculez en production : `./switch_env.sh production`
2. Vérifiez la configuration : `cat .env`
3. Déployez sur O2Switch

### Pour le développement local :
1. Basculez en développement : `./switch_env.bat development`
2. Lancez l'application : `streamlit run app.py`

## ✅ Avantages

- **Séparation claire** entre DEV et PROD
- **Configuration sécurisée** (pas de fuites de secrets)
- **Basculement rapide** entre environnements
- **Git propre** (fichiers .env ignorés)
- **Déploiement sécurisé**
