# 🚀 Gestion Le Kouttâb - Guide de Déploiement Sécurisé

## 📋 Vue d'ensemble

Application de gestion de stock pour Le Kouttâb avec authentification sécurisée, gestion des rôles et export/import de base de données.

**Technologies :**
- Python 3.8+
- Streamlit
- SQLite3
- Sécurité renforcée

---

## 🔐 Configuration de Sécurité Critique

### 1. Fichiers de Configuration

#### `.streamlit/secrets.toml` ⚠️ **OBLIGATOIRE**
```toml
[database]
encryption_key = "votre-clé-de-chiffrement-32-caractères-exactement"

[email_credentials]
sender_email = "votre-email@exemple.com"
sender_password = "votre-mot-de-passe-app"
smtp_server = "smtp.gmail.com"
smtp_port = 587

[admin_setup]
sender_email_admin = "admin@votredomaine.com"

[security]
max_login_attempts = 5
lockout_duration = 900
session_timeout = 3600
```

#### `.htaccess` 🛡️ **Protection Apache**
```apache
# Protéger les fichiers sensibles
<Files "data/stock_kouttab.db">
    Require all denied
</Files>

<Files "*.log">
    Require all denied
</Files>

<Files ".streamlit/secrets.toml">
    Require all denied
</Files>

# Headers de sécurité
Header always set X-Content-Type-Options nosniff
Header always set X-Frame-Options DENY
Header always set X-XSS-Protection "1; mode=block"
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

# Désactiver la signature du serveur
ServerTokens Prod
ServerSignature Off
```

#### `protect_uploads.htaccess` 📁 **Protection Uploads**
```apache
# Interdire l'exécution de scripts dans uploads
<Files "*.php">
    Require all denied
</Files>
<Files "*.py">
    Require all denied
</Files>
<Files "*.sh">
    Require all denied
</Files>

# Autoriser uniquement les images et documents
<FilesMatch "\.(jpg|jpeg|png|gif|pdf|doc|docx)$">
    Require all granted
</FilesMatch>

# Refuser tout le reste
Require all denied
```

---

## 📦 Fichiers Essentiels du Projet

### 🔧 **Configuration**
- ✅ `requirements.txt` - Dépendances Python
- ✅ `.htaccess` - Configuration Apache
- ✅ `protect_uploads.htaccess` - Protection uploads
- ✅ `.streamlit/secrets.toml.example` - Modèle de configuration

### 🐍 **Application principale**
- ✅ `app.py` - Application Streamlit principale
- ✅ `database.py` - Gestion base de données
- ✅ `database_backup.py` - Export/Import BDD

### 🎨 **Interfaces utilisateur**
- ✅ `ui_stock.py` - Gestion stock
- ✅ `ui_admin.py` - Administration
- ✅ `ui_expenses.py` - Notes de frais
- ✅ `ui_invoices.py` - Factures
- ✅ `ui_dashboard.py` - Tableau de bord

### 🔐 **Sécurité**
- ✅ `security.py` - Fonctions sécurité
- ✅ `security_middleware.py` - Middleware sécurité
- ✅ `logger_config.py` - Configuration logs

### 📧 **Utilitaires**
- ✅ `email_utils.py` - Envoi d'emails
- ✅ `admin_setup.py` - Configuration admin
- ✅ `init_admin.py` - Initialisation admin
- ✅ `invitation_manager.py` - Gestion invitations

### 🚀 **Déploiement**
- ✅ `start.sh` - Démarrage Linux
- ✅ `start.bat` - Démarrage Windows

---

## 🛠️ Procédure de Déploiement

### 1. Préparation du Serveur

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Python et pip
sudo apt install python3 python3-pip python3-venv -y

# Installer Apache (si nécessaire)
sudo apt install apache2 -y
```

### 2. Configuration de l'Accès SSH Sécurisé

#### 🔐 **Générer vos clés SSH (sur votre machine locale)**

**Windows (PowerShell/Git Bash) :**
```bash
ssh-keygen -t ed25519 -b 4096 -C "votre-email@exemple.com"
# Ou RSA si ed25519 non supporté :
ssh-keygen -t rsa -b 4096 -C "votre-email@exemple.com"
```

**Linux/macOS :**
```bash
ssh-keygen -t ed25519 -C "votre-email@exemple.com"
```

**Réponses lors de la génération :**
```
Enter file in which to save the key: [Entrée pour défaut]
Enter passphrase: [MOT DE PASSE SÉCURISÉ - OBLIGATOIRE]
Enter same passphrase again: [Répéter le mot de passe]
```

#### 🚀 **Copier votre clé publique sur le serveur**

**Méthode recommandée :**
```bash
ssh-copy-id utilisateur@votre-domaine.com
```

**Manuellement :**
```bash
# Afficher la clé publique
cat ~/.ssh/id_ed25519.pub

# Sur le serveur :
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "votre-clé-publique" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 🛡️ **Sécuriser le serveur SSH**

```bash
# Éditer la configuration SSH
sudo nano /etc/ssh/sshd_config

# Modifier ces lignes :
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
Port 2222  # Optionnel, pour plus de sécurité
AllowUsers votre-utilisateur

# Redémarrer SSH
sudo systemctl restart sshd
```

#### 📱 **Créer un alias de connexion (optionnel)**

```bash
# Sur votre machine locale
nano ~/.ssh/config

# Ajouter :
Host kouttab
    HostName votre-domaine.com
    User votre-utilisateur
    Port 2222
    IdentityFile ~/.ssh/id_ed25519

# Utilisation simplifiée :
ssh kouttab
```

### 3. Configuration de l'Environnement

```bash
# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### 3. Configuration des Permissions

```bash
# Créer les dossiers nécessaires
mkdir -p data uploads logs

# Permissions critiques
chmod 700 data/
chmod 600 data/stock_kouttab.db
chmod 755 uploads/
chmod 700 logs/
chmod 600 .streamlit/secrets.toml
chmod 644 .htaccess
chmod 644 protect_uploads.htaccess
```

### 4. Configuration Apache

```bash
# Activer les modules nécessaires
sudo a2enmod headers
sudo a2enmod rewrite

# Copier la configuration
sudo cp .htaccess /var/www/html/
sudo cp protect_uploads.htaccess uploads/
```

### 5. Démarrage de l'Application

```bash
# Utiliser le script approprié
./start.sh    # Linux
start.bat     # Windows

# Ou directement
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

---

## 🗄️ Accès à la Base de Données après Déploiement

### 🔐 **Accès via SSH**

Une fois déployé, vous pouvez accéder directement à la base de données :

```bash
# Connexion SSH avec clé
ssh utilisateur@votre-domaine.com

# Navigation vers le projet
cd /var/www/html/gestion-stock-kouttab

# Accès SQLite interactif
sqlite3 data/stock_kouttab.db
```

### 📊 **Commandes SQLite utiles**

```bash
# Une fois dans SQLite :
.tables                    # Lister les tables
.schema nom_table         # Voir la structure
SELECT COUNT(*) FROM Stock;  # Compter les articles
SELECT * FROM Admins;     # Voir les administrateurs
.quit                      # Quitter
```

### 🐍 **Script Python d'administration**

Créez un script `db_admin.py` sur le serveur :

```python
#!/usr/bin/env python3
import sqlite3
import sys

DB_PATH = 'data/stock_kouttab.db'

def connect_db():
    return sqlite3.connect(DB_PATH)

def show_tables():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables disponibles:")
    for table in tables:
        print(f"  - {table[0]}")
    conn.close()

def run_query(query):
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        
        if query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            for row in results:
                print(row)
        else:
            conn.commit()
            print(f"{cursor.rowcount} ligne(s) affectée(s)")
    except Exception as e:
        print(f"Erreur: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python db_admin.py [tables|query 'SQL']")
    elif sys.argv[1] == "tables":
        show_tables()
    elif sys.argv[1] == "query" and len(sys.argv) > 2:
        run_query(sys.argv[2])
```

### 🔧 **Permissions pour l'accès BDD**

```bash
# Donner les permissions appropriées
sudo chown -R $USER:www-data data/
sudo chmod 770 data/
sudo chmod 660 data/stock_kouttab.db

# Ajouter votre utilisateur au groupe web
sudo usermod -a -G www-data $USER
```

### 📱 **Tunnel SSH pour accès local**

```bash
# Créer un tunnel pour accéder à l'interface localement
ssh -L 8501:localhost:8501 utilisateur@votre-domaine.com
# Puis http://localhost:8501 dans votre navigateur
```

### 💾 **Backup de la base de données**

```bash
# Script de backup automatique
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
sqlite3 data/stock_kouttab.db ".backup backup_${DATE}.db"
gzip backup_${DATE}.db
echo "Backup créé: backup_${DATE}.db.gz"
```

---

## 🔍 Checklist de Sécurité

### ✅ **Avant déploiement**
- [ ] Configurer `.streamlit/secrets.toml`
- [ ] Définir une clé de chiffrement forte (32 caractères)
- [ ] Configurer les identifiants email
- [ ] Vérifier les permissions des fichiers
- [ ] Configurer `.htaccess`
- [ ] Générer et configurer les clés SSH
- [ ] Sécuriser la configuration SSH du serveur

### ✅ **Après déploiement**
- [ ] Créer le premier admin : `http://domaine:8501?init_admin=true`
- [ ] Tester toutes les fonctionnalités
- [ ] Vérifier les logs de sécurité
- [ ] Configurer HTTPS (SSL/TLS)
- [ ] Mettre en place les backups
- [ ] Vérifier l'accès SSH avec clés
- [ ] Tester l'accès à la base de données

---

## 🚨 Points de Sécurité Critiques

### 1. **Base de données**
- 🔒 Fichier `data/stock_kouttab.db` protégé (600)
- 🚫 Non accessible via web
- 📤 Export exclut la table `Admins`
- 🔐 Accès uniquement via SSH avec clés

### 2. **SSH**
- 🔑 Authentification par clés obligatoire
- 🚫 Connexions par mot de passe désactivées
- 👤 Connexions root interdites
- 📡 Port SSH personnalisé recommandé

### 3. **Sessions**
- ⏱️ Timeout automatique (1h par défaut)
- 🔐 Mot de passe fort requis
- 🚫 Tentatives de connexion limitées

### 4. **Uploads**
- 📁 Dossier `uploads/` protégé
- 🚫 Interdiction scripts exécutables
- ✅ Validation des types de fichiers

### 5. **Logs**
- 📝 Logs de sécurité activés
- 🚫 Fichiers de logs protégés
- 📊 Surveillance des connexions

---

## 🔄 Maintenance

### Quotidienne
- Vérifier les logs d'erreurs
- Surveiller l'espace disque
- Vérifier les connexions suspectes

### Hebdomadaire
- Sauvegarder la base de données
- Mettre à jour les dépendances
- Vérifier les logs de sécurité

### Mensuelle
- Mettre à jour le système
- Réviser les permissions
- Tester la restauration

---

## 📞 Support et Dépannage

### Erreurs communes
1. **ModuleNotFoundError** → Vider le cache Python
2. **Permission denied** → Vérifier les permissions
3. **Database locked** → Redémarrer l'application

### Logs utiles
- `logs/security.log` - Sécurité
- `logs/app.log` - Application
- Logs Apache - Erreurs serveur

---

## 📄 Licence

Ce projet est propriété de Le Kouttâb. Toute reproduction ou distribution non autorisée est interdite.

---

**Dernière mise à jour :** $(date)
**Version :** 1.0.0
**Développeur :** Équipe technique Le Kouttâb
