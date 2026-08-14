# CLAUDE.md — Kouttab Stock React

Guide pour Claude Code et tout LLM travaillant sur ce projet. À lire en début de session.

> **Documentation complète : [`docs/`](docs/README.md).** Ce fichier en est la
> version condensée, orientée contribution. Pour comprendre l'application en
> profondeur — architecture, modèle de données, fonctionnalités, sécurité,
> déploiement, tests — commencer par [`docs/README.md`](docs/README.md).
>
> Avant de modifier quoi que ce soit :
> [`docs/08-PIEGES-ET-BONNES-PRATIQUES.md`](docs/08-PIEGES-ET-BONNES-PRATIQUES.md)
> — les erreurs déjà commises sur ce projet, et ce qu'elles ont coûté.

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
│   │   ├── api/deps.py              # Dependency injection (get_current_user, require_roles)
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (.env)
│   │   │   ├── security.py          # JWT, bcrypt, validations
│   │   │   ├── rate_limit.py        # Limiter slowapi partagé
│   │   │   ├── workflow.py          # Transitions de statut autorisées
│   │   │   ├── errors.py            # Codes d'erreur
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
│   │   │   ├── email.py             # SMTP via fastapi-mail (_send / _send_raw)
│   │   │   ├── files.py             # Upload, validation MIME, confinement
│   │   │   ├── naming.py            # Nomenclature des pièces comptables
│   │   │   ├── pdf.py               # Conversion des justificatifs en PDF
│   │   │   ├── outbox.py            # File d'envoi persistante
│   │   │   ├── compta_dispatch.py   # Orchestration nommage + PDF + file
│   │   │   ├── helloasso.py         # Client API HelloAsso
│   │   │   └── csv_import.py
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
| **Stock** | Articles : `nom` UNIQUE, `categorie`, `sous_categorie`, `quantite`, `seuil_alerte`, `emoji`, **`image_url`** (photo du produit, récupérée au scan ; l'emoji sert de repli), `barcode` UNIQUE, `alert_sent` | — |
| **Categories** | Référentiel des catégories : `nom` UNIQUE, `is_default` | — |
| **SousCategories** | Hiérarchie cat→sous-cat : UNIQUE (`nom_categorie`, `nom_sous_categorie`) | (logique) |
| **Admins** | Utilisateurs : `username` UNIQUE, `password_hash` bcrypt, `role`, `validation_status`, profil (nom, prenom, email, telephone, **rib**) | — |
| **AdminInvitations** | Tokens email : `email` UNIQUE, `token_hash` SHA256, `expires_at`, `used`, `attempts` | — |
| **NotesDeFrais** | Notes de frais avec workflow validation | `id_user → Admins.id` (CASCADE) |
| **FichiersNotesDeFrais** | Pièces jointes notes | `id_note_de_frais` (CASCADE) |
| **Factures** | Factures déposées | `id_user → Admins.id` (CASCADE) |
| **FichiersFactures** | Pièces jointes factures | `id_facture` (CASCADE) |
| **StockModifications** | Workflow d'approbation modif stock | `id_user`, `id_stock`, `approuve_par → Admins.id` |
| **TicketsJustificatif** | Demande de pièce manquante : `libelle` (seul obligatoire), `montant_attendu`, `date_achat`, `fournisseur`, `statut` (`ouvert`·`clos`·`annule`), `rappels_envoyes`, `dernier_rappel_at` | `id_user`, `cree_par`, `closed_by`, `id_facture → Factures.id` |
| **Remboursements** | Un versement à un bénévole soldant N notes : `date_remboursement`, `moyen`, `etablissement`, `approuve_par`, `montant_total` (**instantané**), `chemin_pdf`, `chemin_xlsx` | `id_user`, `cree_par → Admins.id` |
| **CategoriesDepense** | Référentiel administrable de la **nature des dépenses**, demandée sous tous les pôles (`Courses`, `Stock goûter`, `Achat buvette`, `Achat matériel`, `Mobilier, immobilier et petit équipement`, `Fournitures administratives`, `Entretien`, `Réceptions (repas, déplacements, nourriture)`, `Autre`) : `nom` UNIQUE, `is_default`, `is_active`, `ordre` — `Autre` porte `ordre = 99` pour rester en fin de liste | — |
| **BuvetteProducts** | Produits de la buvette synchronisés HelloAsso : `helloasso_tier_id` UNIQUE, `name`, `price_cents`, `quantity`, `seuil_alerte`, `emoji`, `image_url`, `alert_sent`, `last_synced_at`, `is_active` | — |
| **Conversations** | Fil de discussion : `id_user` (auteur), `destinataire` (`compta`·`admin`), `sujet`, `statut` (`ouverte`·`en_cours`·`traitee`), `attente_equipe`, `non_lu_demandeur` (**dénormalisés**, cf. §6) | `id_user`, `closed_by` |
| **ConversationMessages** | Un message : `corps`, `auteur_nom` et `de_l_equipe` **figés à l'écriture** — un compte supprimé laisserait des messages anonymes, un bénévole promu comptable ferait passer ses anciennes questions pour des réponses | `id_conversation` (CASCADE), `id_auteur` |
| **BuvetteSales** | Log idempotent des ventes HelloAsso : `helloasso_order_id`, `helloasso_payment_id`, `helloasso_item_id`, snapshot `product_name_snapshot`, `quantity_sold`, `amount_cents`, infos client, `raw_event` JSON | `buvette_product_id → BuvetteProducts.id` (SET NULL) ; UNIQUE (`helloasso_payment_id`, `helloasso_item_id`) |

**Énumérations (string)**
- `Admins.role` : `Super Admin` · `AdminBenevoles` · `Compta` · `Benevole`
- `Admins.validation_status` : `pending` · `active` · `rejected`
- `NotesDeFrais.status` : `En attente` · `Approuvée` · `Refusée` · `Remboursée`
  — **`Remboursée` ne se déclare pas** : elle est posée par `POST /reimbursements`,
  qui enregistre le versement et produit le justificatif. La liste déroulante y
  menait aussi, sans rien produire : des notes se retrouvaient marquées payées,
  sans document, et le statut étant terminal, sans moyen de corriger. Le retour
  `Remboursée → Approuvée` reste ouvert **tant qu'aucun versement n'est
  rattaché** — c'est la porte de sortie de ces notes-là.
- `Factures.status` : `En attente` · `En cours de traitement` · `Validée` · `Refusée`
- `StockModifications.status` : `En attente` · `Approuvée` · `Refusée`

**Champs sensibles** : `password_hash`, `email`, `telephone`, **`rib`** (TRÈS sensible : accès Super Admin et Compta uniquement), `token_hash`.

**`rib` est chiffré au repos** (AES-256-GCM) par le type de colonne
`ChampChiffre` (`app/db/types.py`), et non par le CRUD : tout ce qui lit ou
écrit `Admin.rib` traverse le chiffrement, y compris le code écrit plus tard.
Ne rien chiffrer ni déchiffrer à la main. La clé vit dans `RIB_ENCRYPTION_KEY`
et **la perdre rend les RIB définitivement illisibles** ; son absence empêche
le démarrage en production. Les valeurs en clair héritées restent lisibles
(préfixe `gcm1:` absent), ce qui rend le déploiement sans coupure.

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
| Notes de frais — archiver / restaurer | — | — | ✅ | ✅ |
| Notes de frais — supprimer définitivement | — | — | — | ✅ |
| Justificatifs — écarter / rétablir | — | — | ✅ | ✅ |
| Justificatifs — ajouter à une note existante | ✅ (la sienne) | ✅ | ✅ | ✅ |
| Notes de frais — remboursement groupé + justificatif | — | — | ✅ | ✅ |
| Remboursements — consulter les siens | ✅ | ✅ | ✅ | ✅ |
| Justificatifs — demander, relancer, clore | — | — | ✅ | ✅ |
| Justificatifs — voir ce qu'on me demande | ✅ | ✅ | ✅ | ✅ |
| Notes de frais — voir RIB utilisateur | — | — | ✅ | ✅ |
| RIB en document — déposer le sien | ✅ | ✅ | ✅ | ✅ |
| RIB en document — télécharger celui d'un autre | — | — | ✅ | ✅ |
| Contact — ouvrir un fil, répondre au sien | ✅ | ✅ | ✅ | ✅ |
| Contact — boîte de l'équipe, statuts | — | — | ✅ (compta) | ✅ (les deux) |
| Factures — déposer | ✅ | ✅ | ✅ | ✅ |
| Factures — changer statut + motif | — | — | ✅ | ✅ |
| Factures — archiver / restaurer | ✅ (les siennes, « En attente ») | — | ✅ | ✅ |
| Admin — valider comptes pending | — | — | — | ✅ |
| Admin — gérer utilisateurs/rôles | — | — | — | ✅ |
| Admin — invitations email | — | — | — | ✅ |
| Admin — Export/Import BDD | — | — | — | ✅ |
| Admin — Import CSV inventaire | — | ✅ | — | ✅ |
| Buvette — consulter stock & ventes | — | ✅ | ✅ | ✅ |
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
- `GET /users/annuaire` — bénévoles inscrits, **lecture seule** (Compta+), sans RIB
- `POST|GET|DELETE /users/me/rib-document` — le RIB en document (PDF ou image)
- `GET /users/{id}/rib-document` — téléchargement par le propriétaire, la
  Compta ou le Super Admin. Le contrôle porte sur le rôle **et** sur la
  propriété : les identifiants se devinent, ils se suivent.

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
- `DELETE /expenses/{id}` — **archiver**, non supprimer (Compta+, note "Remboursée")
- `DELETE /expenses/{id}/definitif` — **effacer pour de bon** (Super Admin seul,
  motif obligatoire, journalisé). Pour le ménage — notes de test, saisies
  fautives — jamais pour une pièce comptable réelle. Emporte les justificatifs
  et, si le versement qui la soldait se retrouve sans aucune note, ce versement
  aussi : un remboursement sans contrepartie ne documente plus rien.
- `POST /expenses/{id}/restore` — défaire l'archivage (Compta+)
- `GET /expenses` — toutes (Compta+) ; `?include_archived=true` pour l'historique
- `PATCH /expenses/{id}/validate` — changer statut + commentaire compta (Compta+)
- `GET /expenses/{id}/files` — liste fichiers
- `POST /expenses/{id}/files` — **ajouter** une pièce à une note existante
  (le déposant tant qu'elle n'est pas remboursée, la comptabilité à tout moment)
- `DELETE /expenses/{id}/files/{file_id}` — **écarter** une pièce (Compta+,
  motif obligatoire, montré au déposant) ; `POST .../restore` la rétablit
- `GET /expenses/{id}/files/{file_id}` — download

### Invoices (Factures)
- `GET /invoices/me` — mes factures
- `POST /invoices` — déposer (multipart). Champs obligatoires : `id_pole`,
  `date_evenement`, et **exactement un** de `id_event` / `evenement_libre`.
  Optionnels : `fournisseur`, `montant`, `commentaire`.
- `GET /invoices` — toutes (filtres statut, date, recherche) ;
  `?include_archived=true` pour l'historique. **Les filtres s'appliquent aussi
  au déposant** : ils étaient ignorés pour lui, si bien que le menu déroulant
  de son écran ne faisait rien.
- `PATCH /invoices/{id}/status` — changer (Compta+), transitions contrôlées.
  Accepte `commentaires_compta` : un refus arrivait sans le moindre motif.
- `DELETE /invoices/{id}` — **archiver**, non supprimer ; `POST /{id}/restore`
  la rétablit (Compta+). Le déposant n'archive que ce qui est « En attente ».
- `GET /invoices/{id}/files/{file_id}` — download
- `POST /invoices/{id}/resend-compta-email` — relancer l'envoi (Compta+)

### Circuit comptable

Au dépôt d'une facture ou d'une note de frais accompagnée de justificatifs :

1. Pôle et événement sont résolus **avant** toute écriture — ils composent le
   nom du fichier, une erreur doit être signalée au déposant.
2. Chaque justificatif est converti en PDF A4 (`services/pdf.py`) et nommé
   `{Pôle}_{Événement}_{AAAA-MM-JJ}.pdf` (`services/naming.py`), avec suffixe
   `-2`, `-3` en cas de collision.
3. L'envoi est inscrit dans `OutboundEmails` **dans la transaction du dépôt**,
   puis tenté immédiatement en tâche de fond.
3 bis. **`EMAIL_ENABLED=false` fait ÉCHOUER l'envoi.** `_send_raw` retournait
   auparavant en silence, et `outbox` marquait la ligne « Envoyée ». La
   production a tourné ainsi jusqu'au 2026-08-13 : écran tout en vert, boîtes
   vides. Ne rien envoyer reste légitime en développement ; le dire « envoyé »
   ne l'est jamais.
4. En cas d'échec : backoff 5/10/20/40/80 min, puis `abandoned`. Le cron
   `scripts/process_outbound_emails.py` reprend la file toutes les 10 minutes.

Les PDF prêts à l'envoi vont dans `OUTBOX_DIR`, **hors** de `uploads/`, car
leurs noms sont prévisibles.

`frontend/src/lib/naming.ts` duplique `services/naming.py` pour afficher au
déposant le nom exact qui sera envoyé. **Les deux modules partagent la même
table de cas de test** : toute divergence casse un test.

### Rattachement d'une pièce : événement ou catégorie

Le pôle décide de ce que le dépôt demande, et lui seul — aucune liste de pôles
n'est écrite en dur, ni au back ni au front :

| `Poles.requiert_evenement` | Le dépôt exige | Nom du PDF comptable |
|---|---|---|
| `true` — EV(T), EV(G), EV(J) | la **catégorie**, plus un événement (référentiel ou saisie libre) **et** sa date | `{Pôle}_{Événement}_{date événement}.pdf` |
| `false` — Frais généraux, Institut, Halaqa, Séjour annuel, ESP-VT | la **catégorie** et une description de l'achat | `{Pôle}_{Catégorie}_{date dépense}.pdf` |

**La catégorie est demandée sous tous les pôles.** Elle était refusée sous les
pôles événementiels, l'événement y tenant lieu de rattachement — mais
l'événement dit *à quelle occasion* la dépense a eu lieu, pas *ce qui a été
acheté*. Le comptable a besoin des deux pour imputer, et il ne recevait la
nature de la dépense que sur la moitié des pièces. Quand les deux coexistent,
**l'événement l'emporte pour nommer le fichier** : sinon les pièces d'un même
événement cesseraient de se ranger ensemble dans sa boîte.

Les pôles EV portent une **famille** (`Poles.type_evenement` : `T`, `G`, `J`)
et ne proposent que les événements de la leur (`Events.type_ev`). Cette famille
se renseigne à la main — HelloAsso ne la connaît pas — et un événement **non
classé reste proposé sous tous les pôles EV** : filtrer strictement viderait
les listes au lendemain de chaque synchronisation.

Une dépense du local — courses, goûter, matériel — n'a pas d'événement : en
exiger un obligeait le déposant à en inventer, et le comptable recevait des
pièces rattachées à des événements fictifs.

La règle est résolue **une seule fois**, dans `crud/rattachement.py`, pour les
factures comme pour les notes de frais : les deux écrans alimentent le même
circuit comptable, et dupliquer la règle finirait par faire diverger ce que
l'un accepte et l'autre refuse.

### Archivage des notes de frais

`DELETE /expenses/{id}` **archive** : la ligne reste en base avec ses
justificatifs, et se restaure. Elle effaçait auparavant la note *et* les
fichiers du disque — une pièce comptable que l'association doit conserver
plusieurs années disparaissait sur un clic, sans trace de son existence.

Le garde-fou est inchangé : seule une note « Remboursée » s'archive. Ranger une
note en cours de traitement la sortirait des listes alors que le bénévole attend
encore son argent.

Les listes excluent les archives par défaut, côté bénévole comme côté
comptabilité. L'écran comptable les affiche sous son filtre « Archivées », avec
la date et l'auteur du rangement.

L'écran comptable filtre par **À traiter · Approuvées · Remboursées · Archivées ·
Toutes**, chacun portant son compte, et s'ouvre sur « À traiter ». Sans ces
filtres, tout s'empilait dans la fiche de chaque bénévole : le travail du jour
se noyait dans les mois précédents, et l'historique n'était consultable qu'en
dépliant les personnes une par une.

### Écarter un justificatif

Une pièce illisible ou mal rattachée ne pouvait ni être retirée ni remplacée :
`attach_file` n'était appelé qu'à la création, et l'écran conseillait même de
« supprimer cette note et la recréer ».

`FichiersNotesDeFrais.ecarte_at` / `ecarte_par` / `motif_ecart` (migration
`f2b9d4e7a1c3`) : la pièce sort du dossier **et du circuit comptable**
(`compta_dispatch` l'ignore), sans quitter la base. Réversible, comme
l'archivage d'une note — une pièce jointe à un dossier reste une trace, même
refusée.

**Le motif est obligatoire** : il est montré au déposant, qui doit savoir ce
qu'on lui reproche. Sans lui, il redépose la même pièce.

Écarter et **ajouter** vont ensemble : livrer le premier sans le second aurait
fait de cet écran un piège, la note se retrouvant sans justificatif et sans
recours.

### Remboursements groupés

La comptabilité rembourse **un bénévole**, pas une note : un virement solde
plusieurs dépenses et produit un justificatif unique (PDF + tableur), calqué sur
le modèle « NDF - Nom Prénom » du client.

- `GET /reimbursements` — tous pour la compta, les siens pour un bénévole
- `POST /reimbursements` — solde N notes d'un même bénévole (Compta+)
- `GET /reimbursements/{id}/document?format=pdf|xlsx` — justificatif, servi
  **depuis la base** (repli disque pour les versements antérieurs). Accessible
  au bénévole concerné : c'est la preuve de son remboursement.
- `GET /reimbursements/by-volunteer` — fiches et totaux dus (Compta+)
- `GET /reimbursements/options` — moyens et établissements, listes **figées**
  (`core/reimbursement_options.py`), servies plutôt que recopiées côté front

Règles portées par `crud/reimbursement.py` :

1. **Tout ou rien** — un lot invalide (notes de deux bénévoles, note déjà payée,
   note non « Approuvée ») est refusé en bloc, avant toute écriture. Rembourser
   trois notes sur quatre en silence ne se verrait qu'au rapprochement bancaire.
2. `montant_total` est un **instantané** : le recalculer ferait bouger un chiffre
   déjà justifié si une note était corrigée ensuite.
3. Documents produits dans `OUTBOX_DIR`, **hors de `uploads/`** (noms
   prévisibles), **et stockés en base** (`contenu_pdf` / `contenu_xlsx`,
   migration `d0f7b2c5e8a9`) : ils étaient la dernière famille de documents
   restée sur le seul disque, donc perdue avec le volume. Le disque n'est plus
   qu'un cache, utile à la file qui joint des fichiers.
4. Mis en file vers la comptabilité **et vers le bénévole**. Il ne recevait
   rien : il apprenait son remboursement sur son compte bancaire et n'avait
   aucune pièce à produire, alors que le document porte son nom. Deux envois
   distincts — le comptable archive une opération, le bénévole reçoit une
   preuve, et les deux ne se disent pas de la même façon.
5. L'écran **Notes de frais → Remboursements** les liste et les télécharge ;
   une note « Remboursée » y renvoie directement.

`app/core/money.py` est le **jumeau de `frontend/src/lib/money.ts`** — même
raison que `naming.py`/`naming.ts` : le front affiche le montant, le back le
grave dans le justificatif. Corriger l'un sans l'autre produit un document qui
contredit l'écran l'ayant déclenché.

### Tickets de justificatif

La comptabilité constate un achat sans facture. Elle ouvrait sa relance de
mémoire, par messages privés, sans trace de qui avait déjà été relancé.

- `GET|POST /tickets` — liste et ouverture (Compta+)
- `PATCH /tickets/{id}` · `POST /tickets/{id}/close` · `POST /tickets/{id}/remind`
- `GET /tickets/me` — ses propres demandes, **tout utilisateur** : contrepartie
  des relances par courriel, pour que le bénévole retrouve la demande dans
  l'application

**Cadence : tous les 3 jours, 5 fois au maximum** (`crud/ticket.py`). Un ticket
jamais relancé l'est immédiatement — le premier rappel part à l'ouverture, mais
peut échouer, et sans ce rattrapage une demande ouverte un vendredi soir
resterait muette tout le week-end. Passé le quota, le ticket reste ouvert mais
se tait : un rappel reçu dix fois finit en filtre, et emporte les suivants.

La **clôture est manuelle**, le rattachement de la facture aussi. Deviner qu'une
pièce déposée correspond à un ticket le fermerait dès que le bénévole dépose
autre chose, et les relances cesseraient alors que la pièce attendue manque.

**Clore un ticket le supprime** — contrairement aux notes et aux factures, qui
s'archivent. Un ticket est une relance, pas une pièce comptable : une fois la
facture reçue, elle est au dossier et la demande ne documente plus rien. Les
tickets clos s'empilaient dans l'écran de la comptabilité sans que personne ne
les relise. Le coût d'une fermeture par erreur est faible — rouvrir une demande,
c'est en créer une nouvelle. Le statut `clos`/`annule` ne survit donc que le
temps de la réponse HTTP et de la ligne de journal.

Les relances sont portées par `scripts/process_outbound_emails.py`, devenu
« file d'envoi et relances programmées ». Un service dédié aurait imposé de
recopier `compose.yml` à la main sur le VPS — étape hors du déploiement
automatique (cf. `DEPLOIEMENT-VPS.md` §13).

### Espace de contact — fils de discussion

Le formulaire d'origine envoyait un courriel et n'en gardait rien : la réponse
partait de la boîte du comptable, hors de l'application. Personne ne pouvait
dire quelles questions restaient sans réponse, ni retrouver ce qui avait été
répondu six mois plus tôt.

- `POST|GET /conversations` — ouvrir un fil, lister les siens (tout authentifié)
- `GET /conversations/equipe` — boîte de l'équipe, filtrée par la portée du rôle
- `GET /conversations/{id}` — le fil ; **l'ouvrir éteint la pastille** du demandeur
- `POST /conversations/{id}/messages` — répondre
- `PATCH /conversations/{id}/statut` — `ouverte` · `en_cours` · `traitee` (équipe)
- `PATCH /conversations/{id}/destinataire` — réorienter un fil mal adressé

**Portée** (`crud/conversation.PORTEE`, jumelée à `ACTIONS.CONVERSATIONS_HANDLE`
côté front) : la Compta lit les fils qui lui sont adressés, le Super Admin les
deux boîtes — il est le recours quand une question a été mal orientée. Un fil se
lit aussi par son auteur, et par personne d'autre : une question de
remboursement porte sur des montants, parfois sur un différend.

Deux propriétés héritées du formulaire tiennent toujours : **l'auteur n'est
jamais saisi** (repris du compte connecté), et **le destinataire est un mot-clé,
pas une adresse** — l'accepter ferait de l'endpoint un relais de courriel ouvert.

`attente_equipe` et `non_lu_demandeur` sont **dénormalisés** sur le fil : ce sont
exactement les deux questions que posent les pastilles à chaque chargement de
page, et les déduire du dernier message imposerait une sous-requête vers une base
distante à chaque fois.

Le courriel subsiste mais **prévient seulement** : le fil est déjà enregistré
quand `outbox.enqueue` est appelé. Un SMTP en panne retarde un avis, il ne fait
plus perdre la question.

**Répondre sur un fil `traitee` le rouvre.** Sans cela, une précision demandée
après coup ne serait jamais lue : le fil est rangé, plus personne ne le regarde.

Pas de temps réel : le fil se recharge à chaque envoi. Une question de bénévole
se traite dans la journée, pas à la seconde.

### Suivi du déposant

`Expense.non_lu_demandeur` et `Invoice.non_lu_demandeur` (migration
`e1a8c3d6f0b2`) reprennent le patron de `Conversation.non_lu_demandeur` :
dénormalisés, allumés par **toute décision de la comptabilité — statut ou
commentaire** —, éteints quand le déposant ouvre sa liste (`crud.*.marquer_lues`,
appelé par l'endpoint qui sert un écran, jamais par la lecture elle-même).

Le commentaire n'allumait rien : il fallait ouvrir « Mes demandes » et repérer
soi-même l'encart. Or c'est souvent lui qui porte la demande de correction.

Les courriels de statut passent désormais par **`outbox`**, comme les envois
comptables. Ils partaient en `_send` best-effort : un SMTP coupé les faisait
disparaître sans trace, alors que c'est le seul avis que reçoit le déposant.

Ils ne mentent plus non plus : un commentaire seul ne s'annonce plus
« votre note a été approuvée » avec un objet rejouant le statut inchangé.

### Notifications
- `GET /notifications/summary` — dossiers en attente pour l'utilisateur
  connecté, **déjà filtrés par ses droits** (un compteur à 0 ne distingue pas
  « rien à traiter » de « pas concerné », et c'est voulu). Alimente les
  pastilles du menu et le rappel affiché une fois par connexion.

### Catégories de dépense
- `GET /expense-categories` — liste (tout authentifié) ; `?include_inactive=true`
- `POST|PATCH|DELETE /expense-categories[/{id}]` — Super Admin. Une catégorie
  `is_default` ou déjà référencée n'est pas supprimable, seulement désactivable.

### Pôles & Événements (référentiels comptables)
- `GET /poles` — liste (tout authentifié) ; `?include_inactive=true`
- `POST|PATCH|DELETE /poles[/{id}]` — Super Admin. Un pôle `is_default` ou
  référencé par une facture n'est pas supprimable, seulement désactivable.
- `GET /events` — liste (tout authentifié), servie depuis le cache local
- `POST /events/sync` — synchronisation HelloAsso (AdminBenevoles+)
- `POST|PATCH|DELETE /events[/{id}]` — AdminBenevoles+

### Admin
- `GET /admin/database/status` — diagnostic
- `POST /admin/database/export` — export ZIP
- `POST /admin/database/import` — import CSVs (Super Admin)
- `GET /admin/outbound-emails` — file des envois comptables (Compta+)
- `GET /admin/outbound-emails/etat` — santé du circuit d'envoi : `EMAIL_ENABLED`,
  SMTP configuré, destinataires, compteurs. Une file vide et un serveur coupé
  se ressemblent — sans ce signal, il faut déposer une pièce pour découvrir
  que rien ne part.
- `POST /admin/outbound-emails/{id}/retry` — relancer un envoi (Compta+)

### Buvette (HelloAsso)
- `GET /buvette/products` — liste produits buvette + stock (AdminBenevoles+ et Compta)
- `POST /buvette/products` — créer un produit manuel (AdminBenevoles+)
- `PATCH /buvette/products/{id}` — ajuster stock / seuil / emoji (AdminBenevoles+)
- `DELETE /buvette/products/{id}` — supprimer (AdminBenevoles+)
- `POST /buvette/sync` — pull les tiers depuis HelloAsso et upsert (AdminBenevoles+)
- `GET /buvette/sales?limit=&offset=` — historique des ventes (AdminBenevoles+ et Compta)
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
- Justificatifs : `pdf|png|jpg|jpeg|heic|heif|webp`. **HEIC** est le format
  par défaut d'iOS dès qu'on dépose depuis « Fichiers » plutôt que depuis la
  photothèque : il était refusé, sur le geste le plus courant de l'application.
  Sa signature est une boîte ISO-BMFF (`ftyp` en 4-8, la marque en 8-12), pas
  une entrée de plus dans la table des signatures — idem WEBP (`RIFF` **et**
  `WEBP`, sinon un WAV passerait).
- **Tout justificatif est converti en PDF à l'enregistrement**
  (`save_upload_file(..., convertir_en_pdf=True)`). Le PDF n'existait
  auparavant que dans `OUTBOX_DIR` pour la pièce jointe, purgé à 30 jours :
  ce qui restait en base et se retéléchargeait était l'image d'origine, d'où
  l'écart visible avec le scanner. La conversion ne dégrade rien — `img2pdf`
  embarque le flux JPEG tel quel. Un PDF déposé reste identique octet pour
  octet. **Rien de rétroactif** : les pièces déjà en base restent des images
  et restent lisibles.
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
- Data fetching : exclusivement via TanStack Query (`useQuery`/`useMutation`), déclaré
  dans `src/api/endpoints/` — jamais de `useQuery` inline dans un composant de page.
- Déclenchement d'une mutation depuis l'UI : `mutation.mutate(vars, { onSuccess })`,
  pas `await mutateAsync` dans un `try/catch`. `useApiMutation` affiche déjà le toast
  d'erreur, donc le `catch` n'aurait rien à faire, et `mutate` ne rejette jamais (pas
  de « unhandled rejection » depuis un `onClick`). `mutateAsync` reste réservé aux cas
  qui exploitent vraiment le résultat dans la foulée (ex. `useBarcodeLookup`, en
  `silentToast`).
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

# Chiffrement du RIB au repos — base64 de 32 octets, IRREMPLAÇABLE
RIB_ENCRYPTION_KEY=

# Sauvegarde des justificatifs vers O2Switch (service `backup` du compose)
BACKUP_SFTP_HOST=sauterelle.o2switch.net
BACKUP_SFTP_USER=
BACKUP_SFTP_DIR=sauvegardes/kouttab-stock

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

---

## 14. Orchestration des skills

Beaucoup de skills sont installés globalement. Ils sont **déjà disponibles** :
rien à installer. Ce qui suit dit lequel utiliser, quand, et surtout lesquels
ignorer. Enchaîner dix skills sur une seule demande dégrade le résultat — chacun
injecte ses instructions et dilue le travail. Viser **un skill principal**, deux
au maximum.

### Déclenchement systématique

| Situation | Skill | Pourquoi |
|---|---|---|
| Auth, upload, secrets, permissions, RIB, webhook HelloAsso, nouvel endpoint | `security-review` | Champs sensibles (§4) et matrice de permissions (§5) : une erreur ici est une fuite, pas un bug d'affichage. |
| Nouvelle fonctionnalité ou correction de bug, **avant** d'écrire le code | `test-driven-development` | Le socle de tests existe (108 front, pytest back) ; le garder vivant coûte moins cher que le reconstruire. |
| Bug, test qui échoue, comportement inattendu | `systematic-debugging` | Éviter de corriger un symptôme sans avoir trouvé la cause. |

### Sur demande explicite

| Demande | Skill |
|---|---|
| « relis ma branche / cette PR » | `code-review` |
| « nettoie / simplifie ce code » | `simplify` |
| Modifier le schéma ou écrire une migration Alembic | `database-migrations` |
| Images, `compose.yml`, conteneurs | `docker-patterns` |
| CI/CD, VPS, mise en production, rollback | `deployment-patterns` |
| Conception d'API, structure FastAPI | `backend-patterns` |
| Cadrer une fonctionnalité avant de coder | `prd` (skill projet) ou `product-capability` |
| Graphiques du tableau de bord (Recharts) | `dataviz` |
| Lancer l'app pour vérifier un changement | `run` |

### À ignorer sur ce projet

`android-clean-architecture`, `recsys-pipeline-architect`, `agent-memory-systems`,
`agent-architecture-audit`, `agent-orchestration-*`, `agent-orchestrator`,
`opensource-pipeline`, `claude-api`, les skills `shopify-*`. Ce projet n'embarque
aucun LLM, aucun agent, et n'est ni une app Android ni une boutique.
`orch-build-mvp` et `orch-pipeline` visent l'amorçage d'un projet neuf : sans
objet ici, l'application existe et tourne.

### Réflexes propres au projet, prioritaires sur tout skill

- **Deux paires de modules jumeaux**, à modifier ensemble : `naming.ts`/`naming.py`
  (nom des pièces comptables) et `money.ts`/`core/money.py` (montant dû au
  bénévole). Le second a été introduit avec les remboursements groupés.
- **`frontend/src/lib/naming.ts` et `backend/app/services/naming.py` sont jumeaux**
  et partagent la même table de cas de test. Modifier l'un sans l'autre casse un
  test — c'est voulu.
- **La base est distante** (O2Switch, jointe par tunnel SSH depuis le VPS) :
  chaque requête coûte un aller-retour réseau. Se méfier des endpoints qui
  enchaînent les requêtes et du lazy-loading des relations.
- **Le schéma DB est partagé avec la version legacy Streamlit.** Toute migration
  se fait sur une base de production réelle : sauvegarde d'abord.
- **Le RIB en document** (`Admins.rib_document`, `deferred`) est en base et
  **sans copie disque**, contrairement aux justificatifs : rien ne l'envoie par
  courriel, donc rien n'a besoin d'un chemin, et une copie de plus d'une donnée
  bancaire serait une surface de fuite de plus. `files.lire_en_memoire` valide
  sans écrire. Le contenu n'est pas chiffré — `ChampChiffre` travaille sur du
  texte, et la protection utile ici est le contrôle d'accès.
- **Les justificatifs sont stockés EN BASE** (`FichiersNotesDeFrais.contenu`,
  `FichiersFactures.contenu`, `LONGBLOB`), et non plus seulement sur le disque
  du VPS : la base est sauvegardée par O2Switch, pas le disque. Décision prise
  sur mesure — 11 Mo pour l'ensemble, 4,5 Mo pour le plus gros fichier ; elle
  serait à revoir au-delà de quelques centaines de mégaoctets.
  - La colonne est **`deferred=True`** : sans cela, lister les notes de frais
    rapatrierait tous les octets de tous les justificatifs depuis une base
    distante.
  - `chemin_fichier` reste renseigné : cache local, trace de l'origine, et
    repli pour les pièces antérieures à la migration `f6b3d1e8a295`.
  - Ce qui exige un chemin (conversion PDF, pièces jointes) passe par
    `files.materialiser`, qui réécrit le fichier depuis la base au besoin.
- **`compose.yml` ne se déploie pas tout seul.** Le workflow ne pousse que les
  images ; le fichier a été copié à la main sur le VPS. Y ajouter un service
  suppose de le recopier là-bas, sans quoi il ne démarrera jamais et rien ne le
  signalera.
- Toucher au déploiement ⇒ mettre à jour `DEPLOIEMENT-VPS.md`, pas
  `DEPLOIEMENT.md` (ce dernier documente l'ancienne cible O2Switch/Passenger).
- **Ne jamais enchaîner les tentatives SSH vers le VPS.** `fail2ban` y bannit
  l'adresse IP après quelques échecs d'authentification, et le bannissement
  survit au redémarrage. Le 2026-08-11, neuf essais pour trouver la bonne clé
  ont coupé le port 22 à tout le bureau, opérateur compris — le serveur
  fonctionnait, mais plus personne ne pouvait s'y connecter. **Au premier
  `Permission denied (publickey)`, s'arrêter et demander.** Le remède passe par
  la console distante IONOS ; procédure complète dans `DEPLOIEMENT-VPS.md` §0.
