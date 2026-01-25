# 🚀 Gestion Le Kouttâb

Application de gestion de stock complète pour Le Kouttâb avec authentification sécurisée, gestion des rôles et interface moderne.

## ✨ Fonctionnalités

- 📦 **Gestion de stock** complète avec catégories et sous-catégories
- 👥 **Gestion des utilisateurs** avec rôles et permissions
- 🔐 **Sécurité renforcée** avec mots de passe hashés et timeout de session
- 📊 **Tableau de bord** avec statistiques en temps réel
- 💰 **Gestion des dépenses** et notes de frais
- 🧾 **Dépôt de factures** avec upload sécurisé
- 📤 **Export/Import** de la base de données
- 🔔 **Notifications** temps réel pour les administrateurs

## 🚀 Installation Rapide

### Prérequis
- Python 3.8+
- pip

### Installation
```bash
# 1. Cloner le projet
git clone <repository-url>
cd gestion-stock-kouttab

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Créer les dossiers
mkdir -p data uploads logs

# 4. Configurer les secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Éditer .streamlit/secrets.toml avec vos informations

# 5. Démarrer
streamlit run app.py
```

### Premier démarrage
1. Allez sur `http://localhost:8501?init_admin=true`
2. Créez le premier compte Super Admin
3. Commencez à utiliser l'application !

## 📋 Documentation

- 📖 **[Installation rapide](README_INSTALL.md)** - Guide d'installation détaillé
- 🔐 **[Sécurité & Déploiement](README_SECURITY.md)** - Guide de déploiement sécurisé

## 🏗️ Architecture

```
├── app.py                 # Application principale
├── database.py            # Gestion base de données
├── ui_*.py               # Interfaces utilisateur
├── security*.py          # Sécurité et authentification
├── .streamlit/           # Configuration Streamlit
├── data/                 # Base de données SQLite
├── uploads/              # Fichiers uploadés
└── logs/                 # Logs de sécurité
```

## 🔐 Sécurité

- ✅ Mots de passe hashés avec bcrypt
- ✅ Protection contre les attaques par force brute
- ✅ Session avec timeout automatique
- ✅ Validation des entrées utilisateur
- ✅ Protection des fichiers sensibles (.htaccess)
- ✅ Logs de sécurité complets

## 👥 Rôles

- **Bénévole** : Gestion du stock de base
- **Admin Bénévoles** : Gestion des utilisateurs et stock
- **Compta** : Gestion des dépenses et factures
- **Super Admin** : Accès complet à toutes les fonctionnalités

## 🛠️ Technologies

- **Backend** : Python 3.8+, SQLite3
- **Frontend** : Streamlit
- **Sécurité** : bcrypt, validation personnalisée
- **Email** : SMTP intégré

## 📞 Support

Pour toute question ou problème :
1. Consultez la documentation
2. Vérifiez les logs dans `logs/`
3. Contactez l'équipe technique

---

**Version** : 1.0.0  
**Développé pour** : Le Kouttâb  
**Licence** : Propriétaire
