# Mise en production — `stock.lekouttab.fr`

Procédure de bascule depuis la redirection Streamlit Cloud actuelle vers
l'application React/FastAPI sur O2Switch.

> Prévoir une fenêtre de ~2 h, de préférence un week-end. Prévenir les
> utilisateurs une semaine avant : les comptes existants restent valides, mais
> le premier mot de passe devra être changé (migration SHA256 → bcrypt).

---

## 0. Avant toute chose — révoquer les secrets compromis

Ces identifiants ont figuré dans l'historique git et doivent être considérés
comme publics, même après la purge de l'historique :

| Secret | Où le changer |
|---|---|
| Mot de passe SMTP `no-reply@lekouttab.fr` | cPanel → Comptes de messagerie |
| Mot de passe d'application Gmail (compte personnel) | Google → Sécurité → Mots de passe d'application |
| `SECRET_KEY` de l'ancienne application | Sans objet : l'application Streamlit est retirée |
| Mot de passe MySQL `sc9bewu6999_stock` | cPanel → Bases de données MySQL |
| `HELLOASSO_CLIENT_SECRET` | admin HelloAsso → Mon compte → API |

Générer ensuite les nouvelles valeurs :

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"   # JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"   # HELLOASSO_WEBHOOK_SECRET
```

---

## 1. Sauvegarder la base

**Non négociable** : la migration ajoute des colonnes à `Factures` et
`NotesDeFrais`.

```bash
mysqldump -u sc9bewu6999_user -p sc9bewu6999_stock \
  > ~/backup_avant_bascule_$(date +%Y%m%d_%H%M).sql
```

Mettre ensuite en place la sauvegarde quotidienne, aujourd'hui inexistante
(cPanel → Cron Jobs, une fois par jour) :

```
0 3 * * * mysqldump -u USER -pMOTDEPASSE BASE | gzip > ~/backups/stock_$(date +\%Y\%m\%d).sql.gz && find ~/backups -name 'stock_*.sql.gz' -mtime +30 -delete
```

---

## 2. Construire le frontend

```bash
cd frontend
npm ci
npm run typecheck && npm run lint && npm run test:run && npm run build
```

Les quatre commandes doivent passer. `dist/` contient le résultat.

---

## 3. Déposer les fichiers

| Source | Destination |
|---|---|
| `frontend/dist/*` | `/www/stock.lekouttab.fr/` |
| `backend/` | `/www/stock.lekouttab.fr/backend/` |
| `.htaccess` (celui de ce dossier) | `/www/stock.lekouttab.fr/.htaccess` |

> ⚠️ Le `.htaccess` **remplace** celui qui redirige vers Streamlit Cloud. C'est
> l'opération qui bascule réellement le service.

Ne pas téléverser : `node_modules/`, `.venv/`, `__pycache__/`, `tests/`,
`.env` local.

---

## 4. Configurer l'application Python

cPanel → **Setup Python App** :

- Python 3.11
- Application root : `/www/stock.lekouttab.fr/backend`
- Startup file : `passenger_wsgi.py`

Puis en SSH, dans l'environnement virtuel créé par cPanel :

```bash
pip install -r requirements.txt
```

Créer `/www/stock.lekouttab.fr/backend/.env` à partir de `.env.example`, en
renseignant notamment :

```
APP_ENV=production
APP_DEBUG=false
JWT_SECRET_KEY=<généré à l'étape 0>
DB_PASSWORD=<nouveau mot de passe MySQL>
SMTP_PASSWORD=<nouveau mot de passe SMTP>
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USE_TLS=false
COMPTA_EMAIL=comptabilite@lekouttab.fr
CORS_ORIGINS=https://stock.lekouttab.fr
UPLOAD_DIR=/home/USER/stock.lekouttab.fr/backend/uploads
OUTBOX_DIR=/home/USER/stock.lekouttab.fr/backend/outbox
HELLOASSO_WEBHOOK_SECRET=<généré à l'étape 0>
```

> L'application **refuse de démarrer** en production si `JWT_SECRET_KEY` vaut
> encore sa valeur par défaut, si `APP_DEBUG` est actif, ou si `CORS_ORIGINS`
> contient une origine en `http://`. C'est volontaire.

---

## 5. Migrer le schéma

La base contient déjà les tables historiques, qu'Alembic ne connaît pas.
**L'ordre compte** :

```bash
cd /www/stock.lekouttab.fr/backend

# 1. Déclarer que les révisions buvette/barcode sont déjà appliquées.
alembic stamp 3c9d1e2f4a02

# 2. Appliquer les nouvelles : tables d'authentification, module comptable.
alembic upgrade head
```

Vérifier :

```bash
alembic current           # doit afficher 6f5b8c3d9e04 (head)
```

> ⚠️ **Ne jamais lancer `alembic revision --autogenerate` sur ce projet.**
> L'historique Alembic ignore les dix tables héritées ; un autogenerate
> produirait des `CREATE TABLE` pour elles et détruirait la production.

---

## 6. Programmer le traitement des envois comptables

cPanel → Cron Jobs, toutes les 10 minutes :

```
*/10 * * * * cd /home/USER/stock.lekouttab.fr/backend && /home/USER/virtualenv/stock.lekouttab.fr/3.11/bin/python scripts/process_outbound_emails.py >> logs/outbox.log 2>&1
```

Ce cron reprend les envois en échec et purge les PDF transmis depuis plus de
30 jours. Sans lui, un mail qui échoue au moment du dépôt ne repartira jamais.

---

## 7. Démarrer et créer le premier administrateur

```bash
touch /www/stock.lekouttab.fr/backend/tmp/restart.txt
curl -s https://stock.lekouttab.fr/api/v1/health      # {"status":"ok",...}

python scripts/create_first_admin_invitation.py prenom.nom@lekouttab.fr
```

Ouvrir le lien affiché et choisir identifiant et mot de passe.

---

## 8. Enregistrer le webhook HelloAsso

Une seule fois, connecté en Super Admin, depuis l'application ou en direct :

```
POST /api/v1/buvette/webhook/configure
```

L'URL enregistrée inclut automatiquement `HELLOASSO_WEBHOOK_SECRET`. Sans ce
secret, l'endpoint est ouvert et n'importe qui peut décrémenter le stock.

---

## 9. Vérifications de bout en bout

- [ ] `https://stock.lekouttab.fr` affiche l'application, pas Streamlit
- [ ] `https://stock.lekouttab.fr/docs` renvoie **404** (fermé en production)
- [ ] `https://stock.lekouttab.fr/backend/uploads/` renvoie **404**
- [ ] Connexion avec un compte existant : changement de mot de passe demandé
- [ ] Administration → les trois pôles sont présents
- [ ] Administration → « Synchroniser depuis HelloAsso » remonte les événements
- [ ] Déposer une facture avec une **photo prise en portrait** : le comptable
      reçoit un PDF A4 **à l'endroit**, nommé `{Pôle}_{Événement}_{Date}.pdf`
- [ ] Administration → « Envois au service comptable » : la ligne est `Envoyé`
- [ ] Avec un compte Bénévole, `/admin` et la validation des notes de frais
      renvoient bien une erreur d'autorisation

---

## En cas de problème

1. Restaurer le `.htaccess` de redirection Streamlit Cloud (service rétabli en
   quelques secondes).
2. Restaurer la base : `mysql -u USER -p BASE < backup_avant_bascule_*.sql`.
3. Consulter `backend/logs/app.log` et `backend/logs/outbox.log`.

Le retour arrière ne perd que les données saisies pendant la fenêtre de
bascule.
