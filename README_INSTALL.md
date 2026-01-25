# 🚀 Gestion Le Kouttâb - Installation Rapide

## 📋 Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de packages Python)
- Accès internet pour l'installation des dépendances

---

## ⚡ Installation en 5 minutes

### 1. Cloner le projet
```bash
git clone https://github.com/votre-repo/gestion-stock-kouttab.git
cd gestion-stock-kouttab
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Créer les dossiers nécessaires
```bash
mkdir -p data uploads logs
```

### 4. Configurer les secrets
```bash
# Copier le modèle de configuration
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Éditer le fichier avec vos informations
nano .streamlit/secrets.toml
```

### 5. Démarrer l'application
```bash
# Linux/macOS
./start.sh

# Windows
start.bat

# Ou directement
streamlit run app.py
```

### 6. Créer le premier administrateur
Ouvrez votre navigateur sur : `http://localhost:8501?init_admin=true`

---

## 🔧 Configuration Rapide

### Fichier `secrets.toml`
```toml
[database]
encryption_key = "clé-de-32-caractères-ici"

[email_credentials]
sender_email = "votre-email@gmail.com"
sender_password = "votre-mot-de-passe-app"
smtp_server = "smtp.gmail.com"
smtp_port = 587

[security]
max_login_attempts = 5
lockout_duration = 900
session_timeout = 3600
```

---

## 🎯 Utilisation

1. **Créer le compte Super Admin** via le lien d'initialisation
2. **Se connecter** avec le compte créé
3. **Ajouter des utilisateurs** via l'interface d'administration
4. **Commencer à utiliser** l'application !

---

## 📁 Structure du Projet

```
gestion-stock-kouttab/
├── app.py                 # Application principale
├── database.py            # Gestion base de données
├── ui_*.py               # Interfaces utilisateur
├── security*.py          # Sécurité
├── .streamlit/           # Configuration Streamlit
├── data/                 # Base de données
├── uploads/              # Fichiers uploadés
├── logs/                 # Logs
└── requirements.txt      # Dépendances Python
```

---

## 🔐 Sécurité

- ✅ Mots de passe hashés avec bcrypt
- ✅ Protection contre les attaques par force brute
- ✅ Session avec timeout automatique
- ✅ Validation des entrées utilisateur
- ✅ Protection des fichiers sensibles

---

## 🆘 Support

En cas de problème :
1. Vérifiez les logs dans `logs/`
2. Consultez `README_SECURITY.md` pour le déploiement
3. Contactez l'équipe technique

---

**Version :** 1.0.0  
**Dernière mise à jour :** $(date)
