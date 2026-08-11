# memory.md — Kouttab Stock React

Mémoire stable du projet : contraintes, décisions architecturales, faits qui ne changent pas (ou peu) entre sessions de développement. Lu en premier par tout LLM qui touche au code.

---

## Domaine métier

- **Client** : association **Le Kouttâb** (institut éducatif). Personne morale qui peut aussi facturer au nom de **E.C.L.A.T**.
- **Utilisateurs** : 4 rôles (`Super Admin`, `AdminBenevoles`, `Compta`, `Benevole`). Bénévoles soumettent des notes de frais et déposent des factures ; admins gèrent stock et utilisateurs ; compta valide les flux financiers.
- **Volume estimé** : < 50 utilisateurs actifs, < 5 000 articles en stock, < 500 notes/factures par mois. Pas besoin de scale horizontal.
- **Buvette HelloAsso** : boutique unique `buvette` sur l'organisation `eclat-education-culture-langues-apprentissage-transmission`. URL admin : `https://admin.helloasso.com/eclat-education-culture-langues-apprentissage-transmission/boutiques/buvette/`. Volume estimé : ~10-30 produits, ~200 ventes/mois.
- **Texte UI** : intégralement en français. Aucune i18n active mais les chaînes sont centralisables dans `src/lib/i18n/fr.ts`.

## Contraintes infrastructure

- **Hébergement imposé : O2Switch mutualisé** (cPanel + Passenger). Pas de Docker, pas de Kubernetes, pas de Redis natif (peut être ajouté en service externe). Pas de workers asynchrones type Celery — pour les tâches longues (envoi mail), accepter le délai synchrone ou utiliser BackgroundTasks de FastAPI.
- **Python 3.11** est la version disponible côté Passenger.
- **Node.js** n'est utilisé que pour le **build** du front. Le runtime O2Switch ne sert que des fichiers statiques pour la SPA.
- **MySQL existe déjà sur O2Switch** avec la BDD `sc9bewu6999_stock`. Les credentials sont dans le cPanel du client. Le schéma actuel (10 tables, cf. `CLAUDE.md` §4) est la **source de vérité** — ne pas le changer sans migration Alembic explicite et accord du client.
- **Domaine** : `stock.lekouttab.fr` (HTTPS automatique O2Switch).
- **SMTP** : `mail.lekouttab.fr:465` TLS, sender `no-reply@lekouttab.fr`. Crédentials côté client.
- **HelloAsso webhook** : URL publique `https://stock.lekouttab.fr/api/v1/buvette/webhook/helloasso`. Doit rester accessible sans auth. À configurer une fois après le go-live via `POST /api/v1/buvette/webhook/configure` (Super Admin).

## Décisions techniques arrêtées

| Décision | Justification |
|---|---|
| **FastAPI** côté back (pas Django, pas Flask) | Async natif, OpenAPI auto, validation Pydantic, courbe d'apprentissage faible pour le dev en charge |
| **React + Vite** côté front (pas Next.js) | App interne, SEO non nécessaire, hébergement statique simple sur O2Switch ; SSR évite la complexité Node runtime sur mutualisé |
| **TanStack Query** pour le data fetching | Cache, refetch, mutations propres ; évite Redux pour le server state |
| **Zustand** pour l'auth uniquement | Léger, pas de boilerplate ; le reste = server state via TanStack |
| **JWT en localStorage + rotation refresh** | Trade-off accepté vs httpOnly cookies (XSS risk modéré sur app interne, simplifie le proxy O2Switch) |
| **bcrypt uniquement** pour les nouveaux mdp | SHA256 du legacy = faible. Migration progressive : flag `password_must_change` au prochain login d'un compte SHA256 |
| **PyMySQL** pas aiomysql | Driver déjà éprouvé en prod sur le legacy ; SQLAlchemy synchrone suffisant pour le volume |
| **Conserver le schéma SQL legacy** | La DB MySQL O2Switch est conservée. Aucune perte de données. Alembic démarre par `stamp head` sur l'existant |
| **Stockage fichiers sur disque** dans `backend/uploads/` | Pas de S3 nécessaire au volume actuel. Path : `{type}/{year}/{month}/{uuid}.ext`. Fichiers protégés par `.htaccess` (jamais accessibles directement, servis via endpoint authentifié) |
| **Texte UI en français, code en anglais** | Le code (variables, fonctions, classes, schemas) est en anglais. Seuls les libellés affichés à l'utilisateur sont en français |
| **Intégration HelloAsso pour la buvette** | Boutique gérée côté HelloAsso (paiements, commandes). Notre app maintient le **stock physique** synchronisé via : (1) sync manuelle des produits (tiers) et (2) webhook entrant qui décrémente le stock à chaque commande. Le stock HelloAsso n'est PAS modifié — chacun garde sa source de vérité. Notre app = stock physique, HelloAsso = caisse / vente |
| **Idempotence webhook stricte** | Contrainte UNIQUE sur `(helloasso_payment_id, helloasso_item_id)` côté `BuvetteSales`. Le webhook retourne 200 même en cas d'erreur (sinon HelloAsso retry en boucle). Toujours logger |

## Mappings importants legacy → nouveau

- `database.py` (legacy) → `app/db/models.py` + `app/crud/*.py`
- `security.py` (legacy) → `app/core/security.py`
- `invitation_manager.py` → `app/services/invitation.py` + `app/crud/invitation.py`
- `email_utils.py` → `app/services/email.py` (templates HTML cette fois)
- `ui_dashboard.py` → `frontend/src/pages/dashboard/`
- `ui_stock.py` → `frontend/src/pages/stock/`
- `ui_expenses.py` → `frontend/src/pages/expenses/`
- `ui_invoices.py` → `frontend/src/pages/invoices/`
- `ui_admin.py` → `frontend/src/pages/admin/`
- `app.py` (Streamlit routing/auth) → `frontend/src/App.tsx` + `frontend/src/stores/auth.ts`
- (nouveau, pas de legacy) → `app/services/helloasso.py` + `app/crud/buvette.py` + `frontend/src/pages/buvette/*`

## Pièges connus du legacy à corriger lors de la réécriture

1. **Logique métier mélangée à Streamlit** (`st.error`, `st.success` dans `database.py`) → la nouvelle couche `crud/` doit être pure et lever des exceptions / retourner des objets.
2. **Sessions volatiles `st.session_state`** → JWT + table `LoginAttempts` ou Redis pour le rate-limit.
3. **`send_invoice_email` cassé** dans le legacy (variables SMTP manquantes) → réécrire proprement via `fastapi-mail`.
4. **Import CSV Streamlit** : `skiprows=6` est fragile → param configurable côté UI.
5. **Pas de transactions explicites** dans plusieurs CRUD legacy → utiliser `with session.begin():` systématiquement pour les opérations multi-tables (notamment `add_expense` + fichiers, `approve_modification` + update Stock).
6. **Toggle MySQL/SQLite** complexe dans le legacy → version React = MySQL only.
7. **`alert_sent` jamais réinitialisé** quand le stock remonte au-dessus du seuil → corriger : reset du flag dès que `quantite >= seuil_alerte`.

## Statuts (énumérations à figer côté code)

```ts
// frontend/src/lib/constants.ts (et identique côté back)
export const ROLES = ['Super Admin', 'AdminBenevoles', 'Compta', 'Benevole'] as const;
export const VALIDATION_STATUS = ['pending', 'active', 'rejected'] as const;
export const EXPENSE_STATUS = ['En attente', 'Approuvée', 'Refusée', 'Remboursée'] as const;
export const INVOICE_STATUS = ['En attente', 'En cours de traitement', 'Validée', 'Refusée'] as const;
export const STOCK_MOD_STATUS = ['En attente', 'Approuvée', 'Refusée'] as const;
```

## Bootstrap initial — état actuel

⚠️ **TEMPORAIRE pour le dev** : le premier Super Admin est créé via `backend/scripts/seed_super_admin.py` (credentials en dur `admin` / `Admin1234!`). À retirer / remplacer avant la mise en prod par un script qui crée une `AdminInvitation` (option A documentée dans `CLAUDE.md` §11.1). Le script `seed_super_admin.py` est idempotent : ne fait rien si l'utilisateur `admin` existe déjà.

**Pourquoi temporaire** : avoir des credentials par défaut connus dans un repo est un risque de sécurité. La cible est un script qui génère un lien d'invitation à usage unique, comme tous les autres admins ensuite.

---

## Hors-scope (Non-Goals)

- Application mobile native (web responsive suffit).
- Multi-tenant (une seule association).
- Intégration comptable externe (Pennylane, Sage, etc.) — export CSV manuel suffit.
- OCR sur les tickets / factures.
- Notifications push / SMS.
- Historique d'audit complet de toutes les actions (uniquement `StockModifications` est tracé).
- Soft-delete (le legacy fait du hard-delete avec CASCADE — on garde ce comportement).

## Références externes

- Schéma SQL de référence : `../create_mysql_structure.sql`
- Code legacy : `../` (parent directory)
- PRD : `prd.md`
- Guide de développement Claude : `CLAUDE.md`
- Guide PRD générique : `prd-guide.md`
