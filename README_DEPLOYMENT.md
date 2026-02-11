# 🚀 Déploiement sur O2Switch - stock.lekouttab.fr

## 📋 Configuration requise

### **1. Configuration O2Switch Set Up Applications**
```
Type d'application: Python/Python Application
Application Root: /www/stock.lekouttab.fr/
Domaine: stock.lekouttab.fr
Fichier de démarrage: app.py
Version Python: 3.11
```

### **2. Fichiers à uploader**

#### **Fichiers principaux :**
- `app.py` - Fichier principal de l'application
- `requirements.txt` - Dépendances Python
- `.htaccess` - Configuration Apache/Streamlit
- `.streamlit/config.toml` - Configuration Streamlit

#### **Tous les fichiers Python :**
- `database.py` - Gestion base de données
- `ui_admin.py` - Interface administration
- `ui_stock.py` - Gestion stock
- `ui_dashboard.py` - Tableau de bord
- `ui_expenses.py` - Gestion dépenses
- `ui_invoices.py` - Gestion factures
- `email_utils.py` - Envoi emails
- `logger_config.py` - Configuration logs
- `csv_import.py` - Import CSV
- `security_middleware.py` - Sécurité
- `database_backup.py` - Sauvegardes

#### **Fichiers de configuration :**
- `env.production` → `.env` (variables d'environnement)

## 🔧 Étapes de déploiement

### **Étape 1 : Préparation locale**
```bash
# Exécuter le script de déploiement
chmod +x deploy.sh
./deploy.sh production
```

### **2. Configuration O2Switch Set Up Applications**
```
Type d'application: Python/Python Application
Application Root: /www/stock.lekouttab.fr/
Domaine: stock.lekouttab.fr
Fichier de démarrage: app.py
Version Python: 3.11
```

#### **Point d'entrée standard**
O2Switch va démarrer votre application Python directement avec `app.py` comme point d'entrée principal.

#### **Fichiers WSGI (optionnel)**
Nous avons créé des fichiers WSGI au cas où O2Switch les demanderait :
- `wsgi_simple.py` : Page HTML qui redirige vers Streamlit
- `wsgi.py` : Version avancée avec démarrage direct

**Utilisez `app.py` comme point d'entrée principal pour O2Switch.**
#### **Fichiers principaux à uploader :**
- `app.py` - Fichier principal de l'application (POINT D'ENTRÉE)
- `requirements.txt` - Dépendances Python
- `.htaccess` - Configuration Apache/Streamlit
- `.streamlit/config.toml` - Configuration Streamlit
- `env.production` → `.env` - Variables d'environnement

#### **Fichiers Python à uploader :**
- `database.py` - Gestion base de données
- `ui_admin.py` - Interface administration
- `ui_stock.py` - Gestion stock
- `ui_dashboard.py` - Tableau de bord
- `ui_expenses.py` - Gestion dépenses
- `ui_invoices.py` - Gestion factures
- `email_utils.py` - Envoi emails
- `logger_config.py` - Configuration logs
- `csv_import.py` - Import CSV
- `security_middleware.py` - Sécurité
- `database_backup.py` - Sauvegardes

#### **Fichiers optionnels (WSGI) :**
- `wsgi_simple.py` - Si O2Switch demande WSGI
- `wsgi.py` - Version avancée WSGI

#### **Fichiers de configuration :**
- `env.production` → `.env` (variables d'environnement)
- `.streamlit/secrets.toml.example` - Exemple pour développement local

### **Étape 2 : Upload via FTP**
1. **Connectez-vous** au FTP O2Switch
2. **Allez dans** `/www/stock.lekouttab.fr/`
3. **Uploadez tous les fichiers**
4. **Renommez** `env.production` en `.env`

### **Étape 3 : Configuration O2Switch**
1. **Allez dans** "Set Up Applications"
2. **Configurez** comme indiqué ci-dessus
3. **Cliquez sur** "Installer"

### **Étape 4 : Vérification**
1. **Accédez à** https://stock.lekouttab.fr
2. **Testez la connexion**
3. **Vérifiez toutes les fonctionnalités**

## 📁 Structure des répertoires sur O2Switch

```
/www/stock.lekouttab.fr/
├── app.py                    # Fichier principal
├── database.py               # Base de données
├── ui_admin.py               # Administration
├── ui_stock.py               # Stock
├── ui_dashboard.py           # Tableau de bord
├── requirements.txt           # Dépendances
├── .htaccess                # Configuration Apache
├── .streamlit/
│   └── config.toml         # Configuration Streamlit
├── .env                     # Variables environnement
├── data/                    # Base de données (créé auto)
│   └── stock_kouttab.db
└── logs/                    # Logs (créé auto)
```

## 🔒 Sécurité

### **Configuration SSL :**
- ✅ HTTPS automatique avec O2Switch
- ✅ Headers de sécurité dans `.htaccess`
- ✅ Protection fichiers sensibles

### **Variables d'environnement :**
- `ENVIRONMENT=production`
- `DATABASE_PATH=/www/stock.lekouttab.fr/data/stock_kouttab.db`
- `SECRET_KEY` - Clé secrète personnalisée

## 🚨 Dépannage

### **Erreurs courantes :**

#### **Erreur 500 :**
- Vérifiez `requirements.txt`
- Regardez les logs O2Switch
- Vérifiez les permissions fichiers

#### **Page blanche :**
- Vérifiez la version Python (3.11)
- Vérifiez le chemin "Application Root"
- Regardez les logs erreurs

#### **Base de données :**
- Créez le répertoire `data/`
- Vérifiez permissions écriture
- Chemin absolu dans `.env`

### **Logs O2Switch :**
1. **Espace client** → "Gestion" → "Logs"
2. **Cherchez** les erreurs Python/Streamlit
3. **Corrigez** selon les messages

## 🎯 Performance

### **Optimisations :**
- Cache activé dans `config.toml`
- Headers de cache dans `.htaccess`
- Compression fichiers statiques
- Base de données SQLite optimisée

## 📞 Support O2Switch

- **Documentation** : https://docs.o2switch.fr/
- **Support** : support@o2switch.fr
- **Base connaissance** : https://faq.o2switch.fr/

---

## ✅ Checklist avant déploiement

- [ ] Tous les fichiers uploadés
- [ ] `env.production` renommé en `.env`
- [ ] Permissions 755 sur répertoires
- [ ] Permissions 644 sur fichiers Python
- [ ] Configuration "Set Up Applications" remplie
- [ ] SSL activé (automatique)
- [ ] Test de toutes les fonctionnalités

---

**URL finale : https://stock.lekouttab.fr** 🚀
