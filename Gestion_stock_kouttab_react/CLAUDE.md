# CLAUDE.md — Kouttab Stock React

Guide pour Claude Code et tout LLM travaillant sur ce projet. À lire en début de session.

---

## 1. Vue d'ensemble

**Kouttab Stock React** est la réécriture moderne d'une application Streamlit/Python existante de gestion de stocks pour l'institut associatif **Le Kouttâb**. La version legacy se trouve dans le dossier parent (`../`). Cette version vise une stack **React + FastAPI** tout en **conservant la base MySQL O2Switch existante**.

L'application gère :
- **Inventaire** d'articles (catégories / sous-catégories / quantités / seuils d'alerte)
- **Notes de frais** des bénévoles avec workflow de validation comptable
- **Factures** déposées par les bénévoles, traitées par la compta
- **Utilisateurs** multi-rôles avec invitations email et validation admin
- **Tableaux de bord** avec KPIs, alertes stock, historique
- **Buvette synchronisée HelloAsso** : produits importés depuis la boutique HelloAsso, stock décrémenté automatiquement à chaque vente via webhook

---

## 2. Stack technique

### Frontend (`frontend/`)
- **React 18 + TypeScript** (Vite)
- **Tailwind CSS** + composants shadcn/ui
- **React Router v6** (routing par rôle)
- **TanStack Query** (data fetching, cache)
- **Zustand** (auth store)
- **React Hook Form + Zod** (formulaires)
- **Recharts** (dashboards)
- **Axios** (HTTP client avec interceptors JWT)

### Backend (`backend/`)
- **FastAPI** (async Python 3.11)
- **SQLAlchemy 2.x** + **Alembic** (ORM, migrations)
- **PyMySQL** (driver MySQL — déjà utilisé en legacy)
- **Pydantic v2** (validation, settings)
- **python-jose** + **passlib[bcrypt]** (JWT, hash passwords)
- **fastapi-mail** (SMTP O2Switch)
- **uvicorn** (dev) / **Passenger WSGI via asgiref** (prod O2Switch)

### Base de données
- **MySQL 8.x sur O2Switch** — schéma identique à la legacy (`../create_mysql_structure.sql` est la référence)
- **12 tables** : 10 héritées du legacy (`Stock`, `Categories`, `SousCategories`, `Admins`, `AdminInvitations`, `NotesDeFrais`, `FichiersNotesDeFrais`, `Factures`, `FichiersFactures`, `StockModifications`) + 2 nouvelles pour la buvette (`BuvetteProducts`, `BuvetteSales`)
- **Charset** : utf8mb4 (emojis, accents)

### Intégrations externes
- **HelloAsso API V5** : OAuth2 client_credentials, lecture boutique `Shop/buvette`, webhook entrant pour les ventes en temps réel.

### Hébergement
- **Production** : O2Switch mutualisé (cPanel + Passenger)
- **Front** servi statiquement (`frontend/dist/`) via Apache + `.htaccess` SPA fallback
- **Back** monté en `/api/*` via Passenger WSGI (`asgiref.WsgiToAsgi(app)`)
- **Domaine** : `stock.lekouttab.fr`

---

## 3. Arborescence cible

```
Gestion_stock_kouttab_react/
├── CLAUDE.md                # CE fichier
├── prd.md                   # Product Requirements Document
├── memory.md                # Mémoire projet (contexte stable)
├── prd-guide.md             # Guide de référence pour rédiger un PRD
├── README.md                # Quick start dev
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (.env)
│   │   │   ├── security.py          # JWT, bcrypt, validations
│   │   │   ├── deps.py              # Dependency injection
│   │   │   └── logger.py
│   │   ├── db/
│   │   │   ├── session.py           # SQLAlchemy engine + sessionmaker
│   │   │   ├── base.py              # declarative Base
│   │   │   └── models.py            # 10 modèles SQLAlchemy
│   │   ├── schemas/                 # Pydantic schemas (request/response)
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── stock.py
│   │   │   ├── expense.py
│   │   │   ├── invoice.py
│   │   │   └── invitation.py
│   │   ├── crud/                    # Business logic pure (no FastAPI)
│   │   │   ├── user.py
│   │   │   ├── stock.py
│   │   │   ├── expense.py
│   │   │   ├── invoice.py
│   │   │   └── invitation.py
│   │   ├── api/v1/
│   │   │   ├── router.py            # Aggrégation des routers
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py          # /login, /signup, /me, /refresh
│   │   │   │   ├── users.py         # /users, validation admins
│   │   │   │   ├── stock.py         # /stock, /categories, /modifications
│   │   │   │   ├── expenses.py      # /expenses + workflow compta
│   │   │   │   ├── invoices.py      # /invoices + upload
│   │   │   │   ├── admin.py         # /admin/* operations
│   │   │   │   └── invitations.py   # /invitations
│   │   │   └── deps.py
│   │   ├── services/
│   │   │   ├── email.py             # SMTP via fastapi-mail
│   │   │   ├── files.py             # Upload, validation MIME
│   │   │   └── invitation.py
│   │   └── utils/
│   ├── alembic/                     # Migrations (read-only après init)
│   ├── tests/                       # pytest
│   ├── uploads/                     # Stockage local fichiers (gitignored)
│   ├── .env.example
│   ├── requirements.txt
│   └── passenger_wsgi.py            # Wrapper WSGI O2Switch
│
└── frontend/
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx                  # Routes
    │   ├── api/
    │   │   ├── client.ts            # Axios instance + interceptors
    │   │   └── endpoints/           # Hooks TanStack Query
    │   │       ├── auth.ts
    │   │       ├── stock.ts
    │   │       ├── expenses.ts
    │   │       ├── invoices.ts
    │   │       └── admin.ts
    │   ├── stores/
    │   │   └── auth.ts              # Zustand auth store
    │   ├── components/
    │   │   ├── ui/                  # shadcn primitives
    │   │   ├── layout/              # Sidebar, TopBar, Layout
    │   │   ├── forms/
    │   │   └── shared/              # PasswordStrength, RoleBadge, ...
    │   ├── pages/
    │   │   ├── auth/                # LoginPage, SignupPage, AdminSetupPage
    │   │   ├── dashboard/           # DashboardPage (4 onglets)
    │   │   ├── stock/               # CategoriesPage, ItemsPage
    │   │   ├── expenses/            # MyExpenses, NewExpense, ValidateExpenses
    │   │   ├── invoices/            # UploadInvoice, ListInvoices
    │   │   └── admin/               # Users, PendingUsers, Categories, ImportCSV
    │   ├── lib/
    │   │   ├── auth.ts              # canAccess(role, page)
    │   │   ├── constants.ts         # ROLES, STATUSES, ICONS
    │   │   └── utils.ts
    │   ├── types/                   # Types TS partagés
    │   └── styles/
    ├── public/
    ├── index.html
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    └── package.json
```

---

## 4. Modèle de données (résumé)

| Table | Rôle | FK clés |
|-------|------|---------|
| **Stock** | Articles : `nom` UNIQUE, `categorie`, `sous_categorie`, `quantite`, `seuil_alerte`, `emoji`, `alert_sent` | — |
| **Categories** | Référentiel des catégories : `nom` UNIQUE, `is_default` | — |
| **SousCategories** | Hiérarchie cat→sous-cat : UNIQUE (`nom_categorie`, `nom_sous_categorie`) | (logique) |
| **Admins** | Utilisateurs : `username` UNIQUE, `password_hash` bcrypt, `role`, `validation_status`, profil (nom, prenom, email, telephone, **rib**) | — |
| **AdminInvitations** | Tokens email : `email` UNIQUE, `token_hash` SHA256, `expires_at`, `used`, `attempts` | — |
| **NotesDeFrais** | Notes de frais avec workflow validation | `id_user → Admins.id` (CASCADE) |
| **FichiersNotesDeFrais** | Pièces jointes notes | `id_note_de_frais` (CASCADE) |
| **Factures** | Factures déposées | `id_user → Admins.id` (CASCADE) |
| **FichiersFactures** | Pièces jointes factures | `id_facture` (CASCADE) |
| **StockModifications** | Workflow d'approbation modif stock | `id_user`, `id_stock`, `approuve_par → Admins.id` |
| **BuvetteProducts** | Produits de la buvette synchronisés HelloAsso : `helloasso_tier_id` UNIQUE, `name`, `price_cents`, `quantity`, `seuil_alerte`, `emoji`, `image_url`, `alert_sent`, `last_synced_at`, `is_active` | — |
| **BuvetteSales** | Log idempotent des ventes HelloAsso : `helloasso_order_id`, `helloasso_payment_id`, `helloasso_item_id`, snapshot `product_name_snapshot`, `quantity_sold`, `amount_cents`, infos client, `raw_event` JSON | `buvette_product_id → BuvetteProducts.id` (SET NULL) ; UNIQUE (`helloasso_payment_id`, `helloasso_item_id`) |

**Énumérations (string)**
- `Admins.role` : `Super Admin` · `AdminBenevoles` · `Compta` · `Benevole`
- `Admins.validation_status` : `pending` · `active` · `rejected`
- `NotesDeFrais.status` : `En attente` · `Approuvée` · `Refusée` · `Remboursée`
- `Factures.status` : `En attente` · `En cours de traitement` · `Validée` · `Refusée`
- `StockModifications.status` : `En attente` · `Approuvée` · `Refusée`

**Champs sensibles** : `password_hash`, `email`, `telephone`, **`rib`** (TRÈS sensible : accès Super Admin et Compta uniquement), `token_hash`.

---

## 5. Matrice de permissions

| Page / Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|---|---|---|---|
| Dashboard (vue + alertes) | ✅ | ✅ | ✅ | ✅ |
| Stock — consulter | ✅ | ✅ | ✅ | ✅ |
| Stock — demander modif | ✅ | — | — | — |
| Stock — modif directe | — | ✅ | — | ✅ |
| Stock — approuver demandes | — | ✅ | — | ✅ |
| Stock — CRUD articles/catégories/sous-cat | — | ✅ | — | ✅ |
| Notes de frais — soumettre | ✅ | ✅ | ✅ | ✅ |
| Notes de frais — éditer ses propres notes "En attente" | ✅ | ✅ | ✅ | ✅ |
| Notes de frais — valider/refuser/rembourser | — | — | ✅ | ✅ |
| Notes de frais — voir RIB utilisateur | — | — | ✅ | ✅ |
| Factures — déposer | ✅ | ✅ | ✅ | ✅ |
| Factures — changer statut | — | — | ✅ | ✅ |
| Admin — valider comptes pending | — | — | — | ✅ |
| Admin — gérer utilisateurs/rôles | — | — | — | ✅ |
| Admin — invitations email | — | — | — | ✅ |
| Admin — Export/Import BDD | — | — | — | ✅ |
| Admin — Import CSV inventaire | — | ✅ | — | ✅ |
| Buvette — consulter stock & ventes | ✅ | ✅ | ✅ | ✅ |
| Buvette — synchroniser produits HelloAsso | — | ✅ | — | ✅ |
| Buvette — CRUD produits / ajuster stock | — | ✅ | — | ✅ |
| Buvette — configurer/supprimer webhook HelloAsso | — | — | — | ✅ |

---

## 6. Endpoints API (v1)

Préfixe : `/api/v1`. Auth : header `Authorization: Bearer <jwt>` (sauf `/auth/*`).

### Auth
- `POST /auth/signup` — créer compte (status `pending`)
- `POST /auth/login` — login → `{ access_token, refresh_token, user }`
- `POST /auth/refresh` — rafraîchir access token
- `POST /auth/logout` — révoquer refresh token
- `GET /auth/me` — utilisateur courant
- `POST /auth/admin-setup` — création Super Admin via token d'invitation
- `GET /auth/validate-invitation?token=&email=` — pré-valider token

### Users
- `GET /users` — liste (Super Admin)
- `GET /users/pending` — comptes en attente (Super Admin)
- `PATCH /users/{id}/validate` — `active|rejected` (Super Admin)
- `PATCH /users/{id}/role` — changer rôle (Super Admin)
- `DELETE /users/{id}` — supprimer (Super Admin)
- `GET /users/me/profile` — profil + RIB
- `PATCH /users/me/profile` — modifier profil + RIB

### Invitations
- `POST /invitations` — créer invitation admin (Super Admin)
- `GET /invitations` — lister
- `DELETE /invitations/{id}` — révoquer

### Stock
- `GET /stock/items` — articles (filtres : catégorie, sous-catégorie, alerte)
- `POST /stock/items` — créer (AdminBenevoles+)
- `PATCH /stock/items/{id}` — modifier (AdminBenevoles+)
- `DELETE /stock/items/{id}` — supprimer (AdminBenevoles+)
- `POST /stock/items/import-csv` — import en lot (AdminBenevoles+)
- `GET /stock/categories` — catégories
- `POST /stock/categories` — ajouter
- `PATCH /stock/categories/{name}` — renommer
- `DELETE /stock/categories/{name}` — supprimer
- `GET /stock/subcategories?category=` — sous-catégories
- `POST /stock/subcategories` — ajouter
- `PATCH /stock/subcategories/{id}` — modifier
- `DELETE /stock/subcategories/{id}` — supprimer
- `GET /stock/statistics` — KPIs dashboard
- `GET /stock/low-stock` — articles en alerte
- `GET /stock/modifications?status=&days=` — historique demandes
- `POST /stock/modifications` — créer demande (Benevole)
- `POST /stock/modifications/{id}/approve` — approuver (AdminBenevoles+)
- `POST /stock/modifications/{id}/refuse` — refuser

### Expenses (Notes de frais)
- `GET /expenses/me` — mes notes
- `POST /expenses` — créer (multipart : tickets en pièces jointes)
- `PATCH /expenses/{id}` — éditer (si "En attente" et propriétaire)
- `DELETE /expenses/{id}` — supprimer (Compta+ si "Remboursée")
- `GET /expenses` — toutes (Compta+)
- `PATCH /expenses/{id}/validate` — changer statut + commentaire compta (Compta+)
- `GET /expenses/{id}/files` — liste fichiers
- `GET /expenses/{id}/files/{file_id}` — download

### Invoices (Factures)
- `GET /invoices/me` — mes factures
- `POST /invoices` — déposer (multipart)
- `GET /invoices` — toutes (filtres statut, date, recherche)
- `PATCH /invoices/{id}/status` — changer (Compta+)
- `GET /invoices/{id}/files/{file_id}` — download

### Admin
- `GET /admin/database/status` — diagnostic
- `POST /admin/database/export` — export ZIP
- `POST /admin/database/import` — import CSVs (Super Admin)

### Buvette (HelloAsso)
- `GET /buvette/products` — liste produits buvette + stock (auth)
- `POST /buvette/products` — créer un produit manuel (AdminBenevoles+)
- `PATCH /buvette/products/{id}` — ajuster stock / seuil / emoji (AdminBenevoles+)
- `DELETE /buvette/products/{id}` — supprimer (AdminBenevoles+)
- `POST /buvette/sync` — pull les tiers depuis HelloAsso et upsert (AdminBenevoles+)
- `GET /buvette/sales?limit=&offset=` — historique des ventes
- `POST /buvette/webhook/helloasso` — **endpoint public** appelé par HelloAsso à chaque commande/paiement
- `GET /buvette/webhook/status` — statut du webhook côté HelloAsso (AdminBenevoles+)
- `POST /buvette/webhook/configure` — enregistre l'URL du webhook chez HelloAsso (Super Admin)
- `DELETE /buvette/webhook` — désinscrit le webhook (Super Admin)

---

## 7. Authentification & sécurité

### JWT
- Access token : 30 min, signé HS256 avec `JWT_SECRET_KEY`.
- Refresh token : 7 jours, stocké côté client (httpOnly cookie ou localStorage selon trade-off — par défaut localStorage + rotation).
- Payload : `{ sub: user_id, role, exp, iat }`.

### Hash mots de passe
- **bcrypt uniquement** pour les nouveaux comptes (`passlib[bcrypt]`).
- Migration : un script porte les anciens hash SHA256 (Streamlit legacy) vers bcrypt en demandant nouveau mot de passe au premier login (flag `password_must_change`).

### Validation mots de passe (signup)
8+ caractères, ≥ 1 majuscule, ≥ 1 minuscule, ≥ 1 chiffre, ≥ 1 caractère spécial.

### Rate limiting
- `slowapi` (in-memory dev, Redis recommandé en prod) :
  - `/auth/login` : 5 tentatives / 15 min / IP+username
  - `/auth/signup` : 3 / heure / IP

### Sessions / lockout
- Géré applicativement côté backend (table `LoginAttempts` ou Redis).
- Lockout de 15 min après 5 échecs successifs.

### Invitations
- Token : `secrets.token_urlsafe(32)`, hashé en SHA256 en DB.
- Expiration 24 h, max 3 tentatives de validation, flag `used` après création.

### Uploads
- MIME validé via lecture des magic bytes + extension whitelist.
- Tailles max : 10 Mo / fichier ; 50 Mo / requête.
- Tickets de frais : `png|jpg|jpeg`. Factures : `pdf|png|jpg|jpeg`.
- Stockage : `backend/uploads/{expenses|invoices}/{year}/{month}/{uuid}.ext` (jamais le nom original direct).

### CORS
- Dev : `http://localhost:5173`.
- Prod : `https://stock.lekouttab.fr` strict.

### Headers sécurité
- HSTS, X-Frame-Options DENY, CSP stricte (déjà dans `.htaccess` legacy à reprendre).

---

## 8. Conventions de code

### Backend
- Python 3.11+, `from __future__ import annotations`.
- Type hints partout, validation Pydantic en frontière.
- `async def` pour endpoints I/O ; SQLAlchemy en mode synchrone OK pour O2Switch (pool 5).
- Pas de `print` : utiliser `logger` configuré (`app.core.logger`).
- Tests : `pytest` + fixtures DB transactionnelles (rollback après chaque test).
- Format : `ruff` + `black` (line length 100).

### Frontend
- TypeScript strict (`strict: true`).
- Composants fonctionnels + hooks.
- Conventions de nommage : `PascalCase` pour composants, `camelCase` pour hooks/utils.
- Pas de logique métier dans les composants : extraire en hooks `use*` ou utils.
- Formulaires : React Hook Form + Zod schema (1 schema par formulaire dans `src/lib/schemas/`).
- Data fetching : exclusivement via TanStack Query (`useQuery`/`useMutation`).
- État global : Zustand minimal (auth seulement). Pour le reste, server state via TanStack Query.
- Format : `prettier` + ESLint.

### Texte UI
**Tout le texte utilisateur reste en français** (cf. legacy). Centraliser dans `src/lib/i18n/fr.ts` pour faciliter une éventuelle i18n.

---

## 9. Configuration / variables d'environnement

### Backend (`.env`)
```
APP_ENV=production            # development | production
APP_DEBUG=false

# Database (O2Switch MySQL)
DB_HOST=mysql.o2switch.net
DB_PORT=3306
DB_USER=sc9bewu6999_user
DB_PASSWORD=
DB_NAME=sc9bewu6999_stock

# JWT
JWT_SECRET_KEY=               # python -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_ACCESS_TOKEN_MINUTES=30
JWT_REFRESH_TOKEN_DAYS=7

# Email SMTP O2Switch
SMTP_HOST=mail.lekouttab.fr
SMTP_PORT=465
SMTP_USER=no-reply@lekouttab.fr
SMTP_PASSWORD=
SMTP_USE_TLS=true
EMAIL_FROM=no-reply@lekouttab.fr

# CORS / URLs
FRONTEND_URL=https://stock.lekouttab.fr
BACKEND_URL=https://stock.lekouttab.fr/api

# Uploads
UPLOAD_DIR=/home/USER/stock.lekouttab.fr/backend/uploads
MAX_UPLOAD_MB=10

# HelloAsso (intégration buvette)
HELLOASSO_API_BASE=https://api.helloasso.com
HELLOASSO_CLIENT_ID=
HELLOASSO_CLIENT_SECRET=
HELLOASSO_ORG_SLUG=eclat-education-culture-langues-apprentissage-transmission
HELLOASSO_BUVETTE_FORM_SLUG=buvette
```

### Frontend (`.env`)
```
VITE_API_URL=https://stock.lekouttab.fr/api/v1
```

---

## 10. Déploiement O2Switch

1. **Build front** localement : `cd frontend && npm run build` → `dist/`.
2. **Upload** via FTP / cPanel :
   - `frontend/dist/*` → `/www/stock.lekouttab.fr/`
   - `backend/` → `/www/stock.lekouttab.fr/backend/`
   - `.htaccess` racine (proxy `/api` + SPA fallback)
3. **cPanel → Setup Python App** :
   - Python 3.11
   - Application root : `/www/stock.lekouttab.fr/backend`
   - Startup file : `passenger_wsgi.py`
4. SSH : `pip install -r backend/requirements.txt`
5. Alembic migrations : `alembic upgrade head` (à lancer une seule fois ; le schéma O2Switch existe déjà — utiliser `alembic stamp head` après création initiale).
6. Restart Passenger (touch `tmp/restart.txt`).

`passenger_wsgi.py` :
```python
from asgiref.wsgi import WsgiToAsgi  # NOTE: Passenger expects WSGI; FastAPI is ASGI.
# Cf. README backend pour le wrapper exact (a2wsgi est l'inverse — utiliser a2wsgi.ASGIMiddleware
# pour exposer une ASGI app à Passenger WSGI).
from a2wsgi import ASGIMiddleware
from app.main import app
application = ASGIMiddleware(app)
```

---

## 11. Pour démarrer en dev

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env                                  # puis remplir
alembic upgrade head                                    # créer les tables
python scripts/create_first_admin_invitation.py <email> # voir §11.1
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```

### 11.1 Bootstrap initial du Super Admin

Le **tout premier compte Super Admin** se crée via un script CLI qui ne fabrique
aucun compte et n'écrit aucun mot de passe :

```bash
python scripts/create_first_admin_invitation.py prenom.nom@lekouttab.fr
```

Le script :
1. Vérifie qu'aucun Super Admin actif n'existe (`--force` pour outrepasser si l'accès est perdu).
2. Crée une `AdminInvitation` directement en DB (sans passer par l'API qui exige un Super Admin).
3. Affiche le lien complet `https://stock.lekouttab.fr/admin-setup?token=...&email=...`
4. L'opérateur ouvre le lien → flow normal `admin-setup` → il choisit lui-même son identifiant et son mot de passe.

> L'ancien `scripts/seed_super_admin.py` a été supprimé : il créait un compte
> `admin` / `Admin1234!` dont le mot de passe était publié dans ce dépôt, et rien
> ne l'empêchait de s'exécuter contre la base de production.

Une fois le premier Super Admin existant, toute création d'admin ultérieure passe par le **flow normal `AdminInvitations`** :
- `POST /api/v1/invitations` (Super Admin connecté) → email envoyé
- L'invité clique le lien → `GET /auth/validate-invitation` (pré-check) → `POST /auth/admin-setup` → compte créé + login

Token : `secrets.token_urlsafe(32)` hashé SHA256 en DB, expiration 24 h, max 3 tentatives, usage unique (`used=true`).

---

## 12. Intégration HelloAsso (Buvette)

### Vue d'ensemble
La buvette de l'association est vendue via une **boutique HelloAsso**
(`https://admin.helloasso.com/eclat-education-culture-langues-apprentissage-transmission/boutiques/buvette/`).
On synchronise les produits dans notre table `BuvetteProducts` et on décrémente le stock
automatiquement à chaque commande grâce au **webhook HelloAsso**.

### Flow d'authentification HelloAsso (OAuth2)
1. `POST https://api.helloasso.com/oauth2/token` avec `grant_type=client_credentials`,
   `client_id`, `client_secret` (form-urlencoded).
2. Réponse : `{ access_token, refresh_token, expires_in: 1799, token_type: "bearer" }`.
3. Cache du token côté backend (en mémoire dans `services/helloasso.py`).
4. Avant expiration, `grant_type=refresh_token` (jamais redemander un nouveau token via
   client_credentials à chaque appel — interdit par HelloAsso).

### Synchronisation des produits
- Endpoint HelloAsso : `GET /v5/organizations/{slug}/forms/Shop/{form_slug}/public`
- Retourne `tiers: [{ id, label, description, amount, ... }]`
- Mapping : `helloasso_tier_id ← tier.id` (UNIQUE), `name ← label`, `price_cents ← amount`
- À l'upsert : si nouveau tier → création avec `quantity=0`, `seuil_alerte=5`. Si existant
  → on **ne touche jamais à `quantity`** (le stock local est notre source de vérité).

### Webhook (ventes en temps réel)
- Configuré côté HelloAsso : `PUT /v5/organizations/{slug}/notifications` body `{"url": "..."}`
- URL pointée : `https://stock.lekouttab.fr/api/v1/buvette/webhook/helloasso`
- Payload reçu : `{ eventType: "Order"|"Payment"|"Form", data: {...}, metadata: null }`
- Sur `Order` : pour chaque `data.items[]`, on appelle `record_sale_and_decrement(...)`
  qui :
  1. Vérifie l'idempotence sur `(payment_id, item_id)` — un même item ne peut pas
     décrémenter le stock deux fois (HelloAsso peut retry).
  2. Trouve le `BuvetteProduct` par `helloasso_tier_id` (peut être `None` si pas encore sync).
  3. Crée une `BuvetteSale` (snapshot du nom du produit).
  4. Décrémente `quantity = max(0, quantity - quantity_sold)`.
  5. Si `quantity < seuil_alerte` ET `alert_sent=false` → envoie email + flag à `true`.
  6. Si `quantity ≥ seuil_alerte` (après remontée manuelle), reset `alert_sent=false`.

### Sécurité du webhook
- Endpoint **public** (pas de JWT — c'est HelloAsso qui appelle).
- Validation stricte du schéma Pydantic ; tout ce qui n'est pas conforme → 422.
- **Toujours** retourner 200 même en cas d'erreur de traitement (sinon HelloAsso retry
  en boucle). Logger l'erreur, ne pas lever d'exception 5xx.
- Idempotence garantie par `UNIQUE(helloasso_payment_id, helloasso_item_id)` côté DB.
- À considérer en v1.1 : whitelist IP HelloAsso ou signature HMAC partagée si HelloAsso
  l'expose un jour.

### Variables d'env requises (cf. `.env`)
```
HELLOASSO_API_BASE=https://api.helloasso.com
HELLOASSO_CLIENT_ID=...
HELLOASSO_CLIENT_SECRET=...
HELLOASSO_ORG_SLUG=eclat-education-culture-langues-apprentissage-transmission
HELLOASSO_BUVETTE_FORM_SLUG=buvette
```

### Fichiers clés
- `backend/app/services/helloasso.py` — client HTTP + cache token
- `backend/app/crud/buvette.py` — logique métier (sync, decrement)
- `backend/app/api/v1/endpoints/buvette.py` — routes
- `backend/app/db/models.py` — `BuvetteProduct`, `BuvetteSale`
- `frontend/src/pages/buvette/*` — UI (liste produits, ventes, modals admin)
- `frontend/src/api/endpoints/buvette.ts` — hooks TanStack

---

## 13. Roadmap & priorités

Voir `prd.md` section 5 (Roadmap). Phasage MVP / v1.1 / v2.0.

Quand tu modifies l'app :
1. Lire `memory.md` pour les contraintes/décisions stables.
2. Vérifier la matrice de permissions (§5) avant tout endpoint sensible.
3. Garder le **schéma DB inchangé** sauf migration explicite avec Alembic.
4. Préférer **éditer** un fichier existant plutôt qu'en créer un nouveau.
5. Mettre à jour ce CLAUDE.md si une convention change.
