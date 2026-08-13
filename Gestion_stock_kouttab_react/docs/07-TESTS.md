# 07 — Stratégie de tests

Ce document décrit comment la suite de tests est lancée, comment elle est
organisée, et surtout **ce qu'elle protège**. Beaucoup de tests de ce dépôt
n'existent pas pour couvrir une ligne de code, mais pour empêcher le retour d'un
incident précis, daté, qui a coûté quelque chose à quelqu'un. Le garde-fou du
courriel (§5) est le plus important d'entre eux.

---

## 1. Comment lancer les tests

### Backend (pytest)

Depuis `backend/`, avec l'interpréteur du projet :

```bash
cd backend
C:\Users\Omar\PycharmProjects\Gestion_Stock_Kouttab\.venv\Scripts\python.exe -m pytest
```

`backend/pytest.ini:2` fixe `testpaths = tests`, il est donc inutile de préciser
un chemin. `addopts = -ra --strict-markers --tb=short` (`backend/pytest.ini:3`)
impose deux choses utiles : un résumé des tests non passants, et le **refus d'un
marqueur non déclaré** — une faute de frappe dans `@pytest.mark.integrration`
fait échouer la collecte au lieu de désactiver silencieusement un test.

Sous-ensembles :

```bash
python -m pytest -m unit             # logique pure, sans HTTP
python -m pytest -m integration      # bout en bout via TestClient
python -m pytest tests/unit/test_aucun_envoi_reel.py -v
```

`asyncio_mode = auto` (`backend/pytest.ini:9`) : les tests `async def` sont
exécutés sans décorateur explicite.

Dépendances de test : `backend/requirements-dev.txt` (`pytest`, `pytest-cov`,
`pytest-asyncio`, `freezegun`, `pypdf` pour inspecter les PDF produits).

> **Linter backend** : `CLAUDE.md` §8 annonce `ruff` + `black`, mais aucun des
> deux n'est présent dans `backend/requirements-dev.txt`, aucun fichier de
> configuration (`ruff.toml`, `pyproject.toml`) n'existe sous `backend/`, et
> `ruff` n'est pas installé dans le `.venv`. Il n'y a donc **aucune commande de
> lint backend exécutable en l'état** — c'est une convention écrite, pas un
> contrôle automatisé.

### Frontend (Vitest, TypeScript, ESLint)

Depuis `frontend/` (scripts déclarés dans `frontend/package.json:7-15`) :

```bash
cd frontend
npm run test:run        # vitest run — une passe, code de sortie exploitable
npm test                # vitest — mode veille pendant le développement
npm run test:coverage   # vitest run --coverage (provider v8)
npm run typecheck       # tsc --noEmit — vérification TypeScript seule
npm run lint            # eslint . --ext ts,tsx
```

`npm run build` enchaîne `tsc && vite build` : le typage est donc revérifié à
chaque build, mais `npm run typecheck` permet de l'obtenir sans produire de
`dist/`.

La configuration Vitest vit dans le bloc `test:` de `frontend/vite.config.ts:39`
(il n'y a **pas** de `vitest.config.ts` séparé). Deux réglages y comptent :

- `environment: 'jsdom'` et `globals: true` ;
- `env: { VITE_API_URL: 'http://localhost:8000/api/v1' }` — commenté sur place
  (`frontend/vite.config.ts:42-44`) : sans cette valeur, les tests hériteraient
  du `VITE_API_URL` relatif de `.env.local` destiné au relais mobile, et msw ne
  reconnaîtrait plus aucune requête interceptée.

Il n'y a **pas de CI** : aucun workflow sous `.github/`. Ces commandes sont à
lancer à la main avant de livrer.

---

## 2. Les chiffres actuels

Relevés en lançant les deux suites le 2026-08-13, sur ce dépôt, à `main`.

### Backend

| Mesure | Valeur |
|---|---|
| Tests exécutés | **540**, tous passants (24 s) |
| Fichiers de test | **56** |
| — `tests/unit/` | 25 fichiers |
| — `tests/integration/` | 27 fichiers |
| — racine `tests/` | 4 fichiers (`test_auth.py`, `test_barcode.py`, `test_buvette.py`, `test_errors.py`) |
| Tests portant `@pytest.mark.unit` | 255 |
| Tests portant `@pytest.mark.integration` | 158 |
| Tests sans marqueur | **127** |

Les 127 tests sans marqueur ne sont pas un détail : `-m unit` et `-m integration`
ne couvrent ensemble que 413 des 540 tests. Les fichiers de la racine, plusieurs
fichiers d'`integration/` (`test_api_contact.py`, `test_api_rib_document.py`,
`test_archivage_factures.py`, `test_suivi_deposant.py`…) et quelques-uns d'`unit/`
(`test_crypto.py`, `test_rib_chiffre_en_base.py`,
`test_migration_chiffrement_rib.py`) n'en posent aucun. **Filtrer par marqueur
n'est donc pas un moyen fiable de tout exécuter** : la commande de référence
reste `pytest` sans filtre.

### Frontend

| Mesure | Valeur |
|---|---|
| Tests exécutés | **183**, tous passants (22 s) |
| Fichiers de test | **27** |

---

## 3. Organisation

### Backend : `tests/unit/` contre `tests/integration/`

La séparation suit la définition inscrite dans `backend/pytest.ini:4-6` :

```
markers =
    integration: tests that hit the API end-to-end
    unit: pure logic tests, no HTTP
```

- **`tests/unit/`** — la logique métier prise seule : `crud/`, `services/`,
  `core/`. Ces tests appellent directement les fonctions, avec une session
  SQLAlchemy quand il en faut une, et ne montent jamais de client HTTP. Ils sont
  rapides et pointent la cause plutôt que le symptôme.
- **`tests/integration/`** — l'API vue du dehors, via `TestClient` : route,
  authentification, permission, code de statut, corps de réponse. C'est le seul
  endroit où la matrice de permissions (`CLAUDE.md` §5) est réellement éprouvée,
  parce qu'un contrôle d'accès ne se vérifie qu'en tentant l'accès.

Les 4 fichiers restés à la racine de `tests/` sont antérieurs à cette
séparation. Ils fonctionnent, ils sont exécutés, mais tout nouveau test a sa
place dans l'un des deux sous-dossiers.

Le marqueur se pose **une fois par fichier**, en tête, jamais test par test :

```python
pytestmark = pytest.mark.unit        # backend/tests/unit/test_aucun_envoi_reel.py:27
pytestmark = pytest.mark.integration # backend/tests/integration/test_api_admin.py:11
```

Aucun `@pytest.mark.unit` ou `@pytest.mark.integration` décoratif n'existe dans
le dépôt : la règle est le `pytestmark` de module.

### Frontend : le test à côté du code testé

Il n'y a pas de dossier `tests/` au front. Deux dispositions coexistent, toutes
deux valides :

- **fichier voisin** — `frontend/src/lib/money.ts` et
  `frontend/src/lib/money.test.ts`, `frontend/src/stores/auth.ts` et
  `frontend/src/stores/auth.test.ts` ;
- **sous-dossier `__tests__/`** — `frontend/src/pages/expenses/__tests__/`,
  `frontend/src/api/endpoints/__tests__/`, employé quand plusieurs tests
  couvrent un même dossier de pages.

Dans les deux cas, le test vit dans le dossier du code qu'il couvre. Un test
loin de son sujet se périme sans qu'on le remarque.

L'outillage partagé est le seul à être centralisé, sous `frontend/src/test/` :

- `frontend/src/test/setup.ts` — chargé par `setupFiles`
  (`frontend/vite.config.ts:46`). Il démarre msw avec
  `server.listen({ onUnhandledRequest: 'error' })`
  (`frontend/src/test/setup.ts:8`) : **toute requête non interceptée fait échouer
  le test** plutôt que de partir dans le vide. Après chaque test, il remet à
  zéro les handlers msw, le DOM, le store d'authentification Zustand, le store
  de toasts et le `localStorage` (`frontend/src/test/setup.ts:9-22`) — c'est
  l'équivalent front de `_isolate_test_state`. Il polyfille ensuite ce que jsdom
  ne fournit pas et que Radix exige : `matchMedia`, `IntersectionObserver`,
  `ResizeObserver`, `scrollIntoView`, les API de capture de pointeur.
- `frontend/src/test/test-utils.tsx` — `renderWithProviders`, qui enveloppe le
  composant dans `QueryClientProvider` + un routeur, et repart d'un store d'auth
  propre. Le `QueryClient` de test désactive les nouvelles tentatives et le cache
  (`retry: false, gcTime: 0, staleTime: 0`,
  `frontend/src/test/test-utils.tsx:20-21`) : sans cela, un test masquerait une
  erreur en la réessayant, et le suivant lirait le cache du précédent.
- `frontend/src/test/mocks/` — `handlers.ts` et `server.ts` de msw.

---

## 4. Les fixtures de `backend/tests/conftest.py`

### La base : une SQLite en mémoire, remise à plat entre chaque test

`backend/tests/conftest.py:79-87` construit un moteur
`sqlite:///:memory:` avec `StaticPool` et `check_same_thread=False` — condition
pour que toutes les sessions voient bien la **même** base en mémoire. Les tables
sont créées une seule fois via `Base.metadata.create_all`.

Deux amorçages suivent, parce que le référentiel de base fait partie de l'état
attendu par le code applicatif : `ensure_default_poles` et
`ensure_default_categories` (`backend/tests/conftest.py:92-97`). En production
ce travail est fait par une migration Alembic et par le `lifespan` au démarrage
— mais ce dernier ouvre une session pointant sur MySQL, pas sur la base de test.

Deux redirections garantissent qu'aucun code n'atteint la vraie base :

1. `app.dependency_overrides[get_db] = _override_get_db`
   (`backend/tests/conftest.py:108`) couvre l'injection FastAPI ;
2. la boucle de `backend/tests/conftest.py:116-123` réécrit `SessionLocal` dans
   `db.session`, `services.outbox` et les endpoints `invoices`, `expenses`,
   `buvette`. Le commentaire dit pourquoi : les traitements différés
   (`BackgroundTasks`, cron de la file d'envoi) ouvrent **leur propre**
   `SessionLocal`, la session de la requête étant déjà fermée quand ils
   s'exécutent. Sans cette réécriture, ils viseraient la base réelle.

`bcrypt.gensalt` est par ailleurs remplacé par une version à 4 tours
(`backend/tests/conftest.py:47-54`). Le hachage reste du vrai bcrypt, seul le
facteur de travail change ; le commentaire chiffre le gain à une dizaine de
minutes sur la suite complète, puisque chaque fixture d'utilisateur en paie le
coût.

> **Nuance à connaître** : `CLAUDE.md` §8 annonce des « fixtures DB
> transactionnelles (rollback après chaque test) ». Ce n'est pas ce qui est
> implémenté, et `_isolate_test_state` explique le choix contraire (voir plus
> bas). La docstring de la fixture le dit explicitement : « contrairement à ce
> qu'annonce le CLAUDE.md ».

### `db_session` — `conftest.py:182`

Ouvre une session sur la base de test et la referme. C'est la porte d'entrée des
tests unitaires qui appellent le CRUD directement, et le socle des fixtures
d'utilisateur.

### `client` — `conftest.py:191`

Un `TestClient` **non authentifié**, monté comme gestionnaire de contexte
(`with TestClient(app) as c`) : la forme `with` déclenche les événements de
cycle de vie de l'application. Sert aux routes publiques (`/auth/login`,
`/auth/signup`, webhook HelloAsso) et à tout test qui vérifie qu'une route
protégée répond bien 401 sans jeton.

### `auth_headers` — `conftest.py:304`

Une **fabrique**, pas une valeur : `auth_headers(user)` rend
`{"Authorization": "Bearer <jwt>"}`. Le jeton est construit directement par
`create_access_token(user.id, user.role)` plutôt que par un aller-retour sur
`/auth/login`. Ce raccourci est délibéré : il évite de payer un login (et le
limiteur de débit) dans chaque test, et surtout il découple les tests de
permission des tests d'authentification — un `/auth/login` cassé ne doit pas
faire tomber les 158 tests d'intégration en cascade.

### `client_authenticated_as` — `conftest.py:319`

La fabrique la plus employée de la suite : `client_authenticated_as(user)` rend
un `TestClient` dont l'en-tête `Authorization` est déjà posé. C'est elle qui
rend lisibles les tests de la matrice de permissions, puisqu'un même appel peut
être rejoué sous quatre rôles en changeant un seul argument :

```python
reponse = client_authenticated_as(compta_user).patch(...)
```

### Les fixtures d'utilisateur par rôle — `conftest.py:266-296`

Cinq fixtures, toutes construites sur `_make_user` (`conftest.py:245`) :

| Fixture | Rôle | Statut |
|---|---|---|
| `super_admin_user` | `Super Admin` | `active` |
| `admin_benevoles_user` | `AdminBenevoles` | `active` |
| `compta_user` | `Compta` | `active` |
| `benevole_user` | `Benevole` | `active` |
| `pending_user` | `Benevole` | **`pending`** |

Elles correspondent exactement aux colonnes de la matrice de permissions
(`CLAUDE.md` §5), plus le cas du compte non validé. Deux détails comptent :

- le nom d'utilisateur est **unique par construction**
  (`_unique_username`, `conftest.py:241`, suffixe `uuid4`) : deux fixtures
  demandées dans le même test ne peuvent pas entrer en collision sur la
  contrainte `UNIQUE` de `Admins.username` ;
- le mot de passe en clair est rattaché à l'instance
  (`user._plain_password`, `conftest.py:262`), ce qui permet aux tests qui
  veulent vraiment passer par `/auth/login` de le faire sans le recopier.

### `first_pole` — `conftest.py:132`

Le pôle « Pôle événementiel » du référentiel de base. La docstring dit pourquoi
la sélection filtre sur `is_default` plutôt que de prendre le premier venu : les
tests créent parfois leurs propres pôles, et un tri par ordre ferait remonter un
pôle ad hoc en tête. C'est le cas « le dépôt exige un événement ».

### `local_pole` — `conftest.py:148`

Le pôle « Local », choisi sur `requiert_evenement is False`. C'est l'autre
branche de la règle de rattachement (`CLAUDE.md` §6) : la dépense sans
événement, qui exige une catégorie. Avoir les deux pôles en fixtures permet de
couvrir la règle sans jamais écrire de nom de pôle en dur dans un test.

### `first_category` — `conftest.py:160`

La première catégorie de dépense du référentiel (« Courses »), compagne de
`local_pole` : un dépôt sur un pôle sans événement en réclame une.

Les trois fixtures de référentiel affirment leur précondition
(`assert poles, "le référentiel de pôles par défaut n'a pas été amorcé"`) : si
l'amorçage saute, l'échec nomme la cause au lieu de produire un `IndexError`
opaque à mi-chemin d'un test d'API.

### `_isolate_test_state` — `conftest.py:196`, `autouse=True`

La fixture qui rend la suite déterministe. Elle ne s'invoque pas : elle
s'applique à tous les tests.

**Ce qu'elle fait**, après chaque test :

1. remet le limiteur de débit à zéro et restaure son état
   (`limiter.reset()`, `conftest.py:217-218`) ;
2. vide toutes les tables **dans l'ordre inverse des dépendances** — tables
   filles d'abord (`reversed(Base.metadata.sorted_tables)`, `conftest.py:223`),
   sinon les clés étrangères s'y opposeraient ;
3. réamorce le référentiel de pôles et de catégories, qui fait partie de l'état
   initial attendu.

Elle désactive aussi le limiteur **pendant** le test (`limiter.enabled = False`,
`conftest.py:215`). La raison est donnée sur place : `TestClient` présente
toujours la même adresse IP, les quotas seraient donc consommés par
l'accumulation des tests plutôt que par le scénario testé — un test de login
échouerait parce qu'un autre fichier a déjà épuisé les 5 tentatives.

**Pourquoi vider les tables plutôt qu'annuler une transaction**, contrairement à
l'usage habituel et à ce qu'annonce `CLAUDE.md` : les endpoints committent, les
traitements différés ouvrent leur propre session, et une transaction externe
partagée via `StaticPool` produirait des interactions difficiles à diagnostiquer.
Le nettoyage explicite coûte quelques millisecondes de plus, mais il est
prévisible.

**Le défaut qu'elle a corrigé** est nommé dans sa docstring : la suite partageait
une base unique sans jamais rien nettoyer, les tests étaient donc sensibles à
leur ordre d'exécution — un pôle créé par l'un faisait échouer l'assertion d'un
autre.

### `captured_emails` — `conftest.py:353`, `autouse=True`

Traitée en détail au §5 : c'est la seconde moitié du garde-fou du courriel.

### `send_raw_reel` — `conftest.py:172`

La **vraie** `_send_raw`, capturée à l'import (`_SEND_RAW_REEL`,
`conftest.py:76`) avant tout remplacement. Les tests qui éprouvent le
comportement de la fonction elle-même — coupe-circuit, TLS — en ont besoin :
passer par `email_service._send_raw` leur donnerait la doublure et les rendrait
inopérants.

---

## 5. Le garde-fou du courriel

**C'est le point le plus important de ce document.**

### Ce qui est arrivé

Le `.env` de développement porte les identifiants SMTP **réels** de
l'association. La suite de tests dépose des factures et des notes de frais, et
le circuit comptable envoie les pièces à la comptabilité. Pendant longtemps,
chaque exécution de `pytest` — plusieurs fois par jour — a donc expédié de
fausses factures dans la boîte de la comptabilité. Le commentaire de
`backend/tests/conftest.py:18-27` va jusqu'à citer l'objet des messages reçus :
« [Facture] EV(T) — Gala d'été 2026 ».

Deux causes distinctes, l'une et l'autre suffisantes :

1. **`EMAIL_ENABLED` restait à `true`**, valeur héritée du `.env` du poste. Le
   coupe-circuit existait déjà dans `services/email.py`, mais rien ne l'armait
   pendant les tests.
2. **La fixture d'interception ne couvrait que `_send`.** Or le circuit
   comptable — celui qui porte les PDF — passe par **`_send_raw`**. C'est
   l'erreur historique : le chemin oublié est précisément celui qui envoyait les
   pièces.

### Protection n° 1 — `EMAIL_ENABLED=false`, posé avant l'import de l'application

`backend/tests/conftest.py:28` :

```python
os.environ["EMAIL_ENABLED"] = "false"
```

**La position de cette ligne est le mécanisme.** Elle est placée en tête du
fichier, avant tout `import` applicatif, et le fichier est explicitement
structuré pour cela : les imports de `app.*` viennent plus bas
(`conftest.py:56-71`) avec des `# noqa: E402` qui signalent que l'ordre est
délibéré. La raison est écrite au-dessus (`conftest.py:11-16`) : l'objet
`settings` est construit **à l'import du premier module applicatif**, et il lit
le `.env` du poste ; ce qui est défini dans l'environnement l'emporte, car
pydantic-settings fait primer les variables d'environnement sur le fichier.
Déplacer cette ligne après un `import app.…` la rendrait sans effet, sans qu'aucun
message ne le signale.

Depuis le correctif du 2026-08-13, `EMAIL_ENABLED=false` ne fait plus sortir
`_send_raw` en silence : elle **lève**. Un envoi désactivé ne peut donc plus être
confondu avec un envoi réussi — ni dans les tests, ni en production (voir
`backend/tests/integration/test_envoi_desactive.py`).

Le même bloc pose aussi `RIB_ENCRYPTION_KEY` (`conftest.py:33-35`) avec une
valeur fixe et sans secret : sans elle, la moindre écriture de RIB lèverait
`CleAbsente`. Elle ne protège rien d'autre qu'une base SQLite en mémoire.

### Protection n° 2 — interception de `_send` **et** de `_send_raw`

La fixture `captured_emails` (`conftest.py:353`) est `autouse=True` : aucun test
ne peut y échapper, y compris ceux qui ne s'intéressent pas au courriel. La
docstring le justifie — empêcher qu'un test joigne par accident un vrai serveur
SMTP, et au passage qu'il se bloque sur le délai d'attente réseau.

Quatre fonctions sont remplacées (`conftest.py:387-394`) :

| Fonction remplacée | Ce qu'elle porte |
|---|---|
| `app.services.email._send` | notifications ordinaires |
| **`app.services.email._send_raw`** | **circuit comptable — les pièces jointes PDF** |
| `app.services.email.send_admin_invitation` | invitations administrateur |
| `app.services.email.send_status_change` | avis de changement de statut |

La doublure de `_send_raw` (`conftest.py:378-385`) porte sa propre docstring, qui
nomme l'incident : « Deuxième barrière après `EMAIL_ENABLED=false` : sans ce
patch, un test rejoignait le vrai serveur SMTP, et la boîte de la comptabilité
recevait les fausses factures de la suite à chaque exécution. »

Les envois capturés sont accumulés dans une liste d'objets `_SentEmail`
(`conftest.py:337`), chacun portant `subject`, `body`, `recipients` et des
`extras` — dont `kind` (`compta`, `admin_invitation`, `status_change`). Les
tests peuvent donc **affirmer sur le courriel sans qu'aucun courriel ne parte**,
ce qui est la seconde raison d'être de la fixture.

### Pourquoi deux protections plutôt qu'une

Elles échouent de manières différentes, donc elles ne tombent pas ensemble.

- `EMAIL_ENABLED=false` couvre **tous** les chemins d'envoi, y compris ceux qui
  n'existent pas encore : une fonction ajoutée demain dans `services/email.py` en
  bénéficie sans que personne n'y pense. Mais elle est fragile à l'ordre des
  imports.
- L'interception couvre nommément quatre fonctions, donc elle rate ce qu'on
  oublie d'y inscrire — c'est exactement ce qui s'est produit avec `_send_raw`.
  En revanche elle est insensible à l'ordre des imports, et elle donne aux tests
  de quoi vérifier le contenu des messages.

Chacune rattrape la faiblesse de l'autre.

### `tests/unit/test_aucun_envoi_reel.py` — le garde-fou du garde-fou

Ce fichier n'existe pas pour tester une fonctionnalité. Il existe pour que les
deux protections **ne puissent plus sauter en silence**. Sa docstring
(`backend/tests/unit/test_aucun_envoi_reel.py:1-15`) raconte l'incident et
annonce l'intention : « Ces tests échouent si l'une ou l'autre protection saute. »

Trois tests, un par propriété à tenir :

**`test_le_coupe_circuit_est_arme`** — `test_aucun_envoi_reel.py:30`

Lit `settings.email_enabled` et exige `False`. Ce test attrape le cas où la ligne
28 du `conftest.py` serait déplacée sous un import applicatif, supprimée, ou
neutralisée par un changement dans la façon dont `settings` est construit. Le
message d'échec renvoie explicitement au `conftest.py` et dit ce qui se passerait
sinon : « les envois partent vers le vrai serveur de l'association ».

**`test_les_deux_chemins_d_envoi_sont_interceptes`** — `test_aucun_envoi_reel.py:38`

Le cœur du fichier, et la réponse directe à l'erreur historique. Il boucle sur
`("_send", "_send_raw")`, récupère l'attribut sur le module `app.services.email`,
puis **inspecte le module dont provient la fonction** :

```python
module = inspect.getmodule(fonction)
assert module is not None and module.__name__.startswith("tests"), (
    f"{nom} n'est pas interceptée : un test peut joindre un vrai serveur SMTP."
)
```

Le contrôle est structurel, pas déclaratif : il ne vérifie pas qu'un
`monkeypatch.setattr` a été écrit quelque part, il vérifie que la fonction
réellement atteignable **appartient au paquet de tests** et non au code
applicatif. Si quelqu'un retire la ligne qui remplace `_send_raw`, la fonction
redevient celle de `app.services.email`, le nom de module ne commence plus par
`tests`, et l'assertion tombe. Le fait de tester `_send` **et** `_send_raw` dans
la même boucle est délibéré — c'est le second qui manquait.

**`test_un_envoi_comptable_est_capture_et_non_expedie`** — `test_aucun_envoi_reel.py:50`

Le test de bout en bout de la doublure : il appelle vraiment
`email_service._send_raw("[Facture] Essai", ...)` et vérifie que le message
atterrit dans `captured_emails`, avec le bon destinataire et
`extras["kind"] == "compta"`. Les deux tests précédents contrôlent la mécanique
(le drapeau, l'origine des fonctions) ; celui-ci contrôle le **résultat** — un
envoi comptable aboutit dans une liste en mémoire, jamais sur le réseau.

### Le pendant en production : `tests/integration/test_envoi_desactive.py`

Fichier complémentaire, à ne pas confondre. `test_aucun_envoi_reel.py` protège
les tests ; `test_envoi_desactive.py` protège la production contre l'excès
inverse — un envoi désactivé qui s'affiche « Envoyé ».

Sa docstring (`backend/tests/integration/test_envoi_desactive.py:1-21`) date
l'incident : le 2026-08-13, la production tournait avec `EMAIL_ENABLED=false`,
l'écran des envois comptables affichait **tout en vert**, et rien ne partait —
ni les pièces au comptable, ni les changements de statut, ni les relances. La
cause tenait en deux lignes : `_send_raw` sortait en silence, et
`outbox._deliver` interprétait ce retour comme une livraison.

Ce fichier importe les **vraies** fonctions au chargement du module
(`test_envoi_desactive.py:26-28`), avec le commentaire qui l'explique :
« Capturées à l'import, donc AVANT que la fixture `captured_emails` ne les
remplace ». Il vérifie ensuite que l'envoi réel **lève** au lieu de se taire, que
le motif de l'erreur nomme la variable `EMAIL_ENABLED` — « c'est ce qui
transforme un mystère de trois semaines en correction de trente secondes » — et
que la file marque `STATUS_FAILED` avec `sent_at is None`
(`test_envoi_desactive.py:50`).

---

## 6. Conventions d'écriture des tests

Ces conventions sont particulières à ce dépôt et il faut les respecter.

### a) Les noms de tests sont en français et décrivent le comportement attendu

Pas le nom de la fonction appelée, pas « test_create_expense_ok ». Le nom d'un
test se lit comme une **phrase affirmative sur ce que le système doit faire**.

Exemple, `backend/tests/integration/test_remboursee_passe_par_le_versement.py:48` :

```python
def test_la_liste_deroulante_ne_permet_plus_de_declarer_un_remboursement(
    client_authenticated_as, benevole_user, compta_user, db_session
):
```

Le nom seul suffit à comprendre la règle métier : « Remboursée » se constate, elle
ne se déclare pas. En cas d'échec, le rapport de pytest nomme la règle violée, ce
qu'un `test_patch_expense_status_422` ne ferait pas.

Autre exemple, `backend/tests/integration/test_envoi_desactive.py:50` :

```python
async def test_la_file_marque_l_echec_et_non_l_envoi(db_session, monkeypatch):
```

Le contraste porté par le nom — « l'échec et non l'envoi » — **est** l'incident.

Côté front, la même règle passe par le libellé de `it(...)`, en français :

```ts
it('annonce le versement : date et montant, sans avoir à déplier', () => {
// frontend/src/pages/expenses/__tests__/ReimbursementsList.test.tsx:50
it('ne propose pas un document absent', async () => {
// frontend/src/pages/expenses/__tests__/ReimbursementsList.test.tsx:81
```

### b) La docstring dit **pourquoi** le test existe : quel défaut réel il empêche de revenir

C'est la convention la plus caractéristique du dépôt. La docstring n'explique pas
ce que le test fait — le code le dit déjà — mais **quel incident a rendu ce test
nécessaire**, souvent avec sa date et son coût.

`backend/tests/integration/test_envoi_desactive.py:50-51` :

```python
async def test_la_file_marque_l_echec_et_non_l_envoi(db_session, monkeypatch):
    """Le cœur de la panne : la ligne passait à « Envoyé » sans rien envoyer."""
```

`backend/tests/unit/test_sql_dialect_compat.py:70-75` :

```python
def test_the_guard_actually_catches_nulls_last() -> None:
    """Le garde-fou doit echouer sur la construction fautive.

    Sans cette verification, une erreur dans `_verifier` rendrait tous les
    tests ci-dessus verts sans rien controler.
    """
```

Les docstrings de module vont plus loin encore, et servent de mémoire du projet.
`backend/tests/integration/test_remboursee_passe_par_le_versement.py:1-18`
énumère les deux chemins qui menaient au statut terminal, dit lequel ne
produisait rien, et conclut : « C'est exactement ce qui est arrivé le 2026-08-13
sur une note de 10,37 €. »

Le front suit la même règle, en JSDoc.
`frontend/src/pages/expenses/__tests__/ReimbursementsList.test.tsx:6-14` :

```ts
/**
 * L'écran des remboursements.
 *
 * Il n'existait pas. Le PDF et le tableur étaient produits à chaque versement,
 * joints au courriel de la comptabilité, et montrés à personne : le bénévole
 * voyait une pastille verte sur sa note et rien d'autre — ni date de versement,
 * ni montant, ni preuve à produire. L'API l'autorisait pourtant déjà à
 * télécharger le sien.
 */
```

Un test sans cette docstring est un test qu'on supprimera un jour parce que
personne ne saura plus ce qu'il retenait.

### c) On teste le comportement observable, pas l'implémentation

Ce qui est affirmé, c'est ce qu'un utilisateur ou un appelant peut constater :
un code de statut HTTP, un contenu de réponse, un texte à l'écran, une ligne en
base, un message dans la liste des envois capturés.

- Côté API, on passe par le client HTTP, jamais par l'appel interne :
  `client_authenticated_as(compta_user).patch(...)` puis
  `assert reponse.status_code == 422`
  (`test_remboursee_passe_par_le_versement.py:53-57`). Le test survit à une
  réorganisation du CRUD, il ne tombe que si le comportement change.
- Le contenu du message d'erreur est lui-même traité comme observable, parce
  qu'il est lu par un humain : le commentaire de
  `test_remboursee_passe_par_le_versement.py:59-60` justifie l'assertion — « Le
  message doit dire par où passer, sinon le comptable croit à un bug après avoir
  cliqué sur un choix que l'écran lui proposait. »
- Côté front, les tests interrogent le DOM rendu (`screen.getBy…`) et simulent
  des gestes réels avec `userEvent`, plutôt que d'inspecter des états internes de
  composant.
- `test_les_deux_chemins_d_envoi_sont_interceptes` est l'exception assumée : il
  inspecte bien l'implémentation (le module d'origine d'une fonction), parce que
  la propriété à garantir **est** une propriété de l'implémentation. Une
  exception, pas un modèle.

---

## 7. Les tests qui protègent une décision

Certains tests ne couvrent pas un comportement mais **verrouillent un choix
d'architecture**. Ils échouent quand quelqu'un défait la décision sans le savoir.
C'est voulu, et ils doivent être lus comme tels avant d'être « corrigés ».

### `tests/unit/test_sql_dialect_compat.py` — l'écart entre SQLite et MariaDB

**Ce qu'il garde** : la suite tourne sur SQLite, la production sur **MariaDB**.
SQLite est permissif ; il accepte des constructions que MariaDB refuse. Une
requête peut donc traverser les 540 tests en vert et renvoyer une 500 en ligne.

**L'incident** (`test_sql_dialect_compat.py:1-13`) : le 2026-08-11,
`ORDER BY ... NULLS LAST` — syntaxe PostgreSQL tolérée par SQLite — faisait
échouer `GET /events` avec l'erreur MariaDB 1064. La liste des événements restait
vide au dépôt d'une facture, **sans message**.

**Le mécanisme** : les requêtes sont compilées avec le dialecte MySQL
(`stmt.compile(dialect=mysql.dialect())`, `test_sql_dialect_compat.py:30-31`)
**sans être exécutées**. On attrape ainsi la syntaxe invalide sans exiger un
serveur MariaDB en CI. Le SQL produit est ensuite fouillé pour quatre
constructions interdites (`CLAUSES_INTERDITES`, `test_sql_dialect_compat.py:27`) :
`NULLS LAST`, `NULLS FIRST`, `DISTINCT ON`, `ILIKE` — toutes du PostgreSQL que
SQLite laisse passer.

Le fichier se protège lui-même : `test_the_guard_actually_catches_nulls_last`
(`test_sql_dialect_compat.py:70`) construit délibérément une requête fautive et
exige que `_verifier` lève. Sans ce test-là, une erreur dans `_verifier` rendrait
tous les autres verts sans rien contrôler.

### Le jumelage `naming.py` / `naming.ts` — et `money.py` / `money.ts`

**Ce qu'il garde** : le front affiche au déposant le nom exact du fichier qui
sera envoyé au comptable. Deux implémentations existent donc pour une seule
règle. Le garde-fou n'est pas un test de comparaison automatique — c'est une
**table de cas partagée, recopiée des deux côtés**.

- `backend/tests/unit/test_naming.py:29-62` — la table paramétrée de
  `slugify_component` : accents, ligatures (`Cœur & Âme` → `Coeur-et-Ame`),
  symboles (`Tarif 50€` → `Tarif-50EUR`), caractères interdits par Windows,
  traversée de chemin (`chemin/../../etc/passwd` → `chemin-etc-passwd`), noms
  réservés (`CON` → `_CON`), scripts non translittérables (`日本語` → `MISSING`).
- `frontend/src/lib/naming.test.ts:19-41` — **les mêmes lignes**, dans le même
  ordre, avec les mêmes commentaires de section.

La docstring de `test_naming.py:1-8` énonce la règle : « Table de cas
volontairement exhaustive : chaque ligne correspond à une façon concrète de
casser un nom de fichier chez le destinataire. […] Le fichier jumeau rejoue la
même table, ce qui garantit que l'aperçu affiché au déposant correspond au
fichier réellement envoyé. »

Le même dispositif existe pour les montants —
`backend/tests/unit/test_money.py:1-9` : « Les deux modules doivent rendre le
même chiffre sur les mêmes données. Le front l'affiche au bénévole et à la
comptabilité ; le back le grave dans le justificatif remis puis dans
`Remboursements.montant_total`. Une divergence produirait un document
contredisant l'écran qui l'a déclenché. » Et la consigne opératoire :
« Les cas ci-dessous sont ceux de `money.test.ts` — les compléter d'un côté
suppose de les compléter de l'autre. »

**Conséquence pratique** : modifier `naming.py` ou `money.py` sans toucher au
jumeau TypeScript casse un test. Ce n'est pas un faux positif à contourner,
c'est le rappel qu'un second fichier attend la même modification.

> Détail à corriger un jour : la docstring de `test_naming.py:5` désigne
> `frontend/src/lib/__tests__/naming.test.ts`, alors que le fichier se trouve en
> réalité en `frontend/src/lib/naming.test.ts`. Le chemin cité est périmé, pas
> le mécanisme.

### `tests/unit/test_migration_*.py` — les migrations exécutées pour de vrai

**Ce qu'ils gardent** : une migration Alembic ne tourne **qu'une fois**, sur la
base de production, souvent sur la donnée la plus sensible du projet. Il n'y a
pas de seconde chance et pas de mode d'essai. Ces tests chargent le fichier de
migration par son chemin, montent une base SQLite jetable, et **exécutent
réellement `upgrade()` puis `downgrade()`** via `MigrationContext` et
`Operations`.

- **`test_migration_chiffrement_rib.py`** garde la migration
  `a1c8e6f2b307_chiffrer_les_rib_existants`. Sa docstring : « Elle ne tourne
  qu'une fois, sur la base de production, sur la donnée la plus sensible du
  projet. Une erreur y est irrattrapable : autant l'avoir vue tourner. » Le test
  monte une table `Admins` réduite (`id`, `rib`), pose une clé de chiffrement
  jetable, et vérifie le passage en clair → chiffré et le retour.
- **`test_migration_justificatifs.py`** garde
  `f6b3d1e8a295_justificatifs_en_base`, qui charge en base les justificatifs
  jusque-là stockés sur le seul disque. Sa docstring : « Elle ne tourne qu'une
  fois, sur des pièces comptables à conserver plusieurs années. Un fichier manque
  à l'appel et c'est un justificatif perdu : autant l'avoir vue tourner sur des
  cas tordus avant de la lancer en production. » Le test crée des fichiers
  réels sous `tmp_path` et vérifie qu'ils arrivent bien en base.

La décision protégée est double : le chargement du fichier par chemin absolu
(`Path(__file__).resolve().parents[2] / "alembic" / "versions" / …`,
`test_migration_justificatifs.py:22-26`) fait que **renommer ou supprimer le
fichier de migration casse le test** — ce qui est le comportement voulu pour une
migration déjà appliquée en production.

---

## 8. Ce que les tests ne couvrent pas

540 + 183 tests verts ne veulent pas dire que l'application fonctionne. Trois
domaines entiers échappent à la suite et se vérifient **à la main**.

### a) Le parcours réel dans le navigateur

Il n'y a **aucun test de bout en bout** : pas de Playwright, pas de Cypress, rien
qui pilote un vrai navigateur. Les tests front tournent dans jsdom, avec msw en
lieu et place du backend, et les tests backend n'ont pas d'interface. Personne ne
vérifie automatiquement que le front et le back s'entendent : msw répond ce que
les handlers de `frontend/src/test/mocks/handlers.ts` disent, pas ce que FastAPI
renverrait.

À vérifier soi-même, dans un navigateur :

- l'enchaînement complet connexion → dépôt d'une pièce → traitement comptable ;
- tout ce qui touche à la **caméra** : le scanner de justificatifs et le lecteur
  de codes-barres appellent `getUserMedia`, que jsdom ne fournit pas et que les
  navigateurs réservent aux origines sécurisées — d'où le mode
  `MOBILE=1 npm run dev` en HTTPS (`frontend/vite.config.ts:7-17`) ;
- le rendu réel : Tailwind, la mise en page, le responsive, l'impression. `css:
  false` (`frontend/vite.config.ts:47`) : les feuilles de style ne sont même pas
  chargées pendant les tests ;
- les avertissements d'accessibilité que la suite laisse passer en `stderr` sans
  échouer (`Missing Description or aria-describedby for DialogContent`, visible
  dans la sortie de `EcartJustificatif.test.tsx`).

### b) L'envoi effectif des courriels

C'est le revers assumé du §5 : puisque **rien ne part jamais** pendant les tests,
rien ne prouve que quelque chose parte en vrai. Ne sont couverts par aucun test :

- la connexion SMTP elle-même — hôte, port, TLS, identifiants ;
- le rendu des messages dans un client de messagerie réel ;
- l'arrivée effective des pièces jointes PDF chez la comptabilité ;
- le classement en indésirable, SPF/DKIM, les limites de l'hébergeur.

La suite garantit qu'un envoi est **demandé**, avec le bon destinataire, le bon
objet et le bon type ; elle ne garantit pas qu'il **arrive**. Après un
déploiement, l'écran `GET /admin/outbound-emails/etat` sert précisément à cela :
il expose `EMAIL_ENABLED`, la configuration SMTP et les compteurs, parce qu'« une
file vide et un serveur coupé se ressemblent » (`CLAUDE.md` §6).

### c) Le comportement sur la base MySQL de production

**Les tests tournent sur SQLite en mémoire** (`backend/tests/conftest.py:80`), la
production sur MariaDB, hébergée chez O2Switch et jointe par tunnel SSH depuis le
VPS. `test_sql_dialect_compat.py` ne referme qu'une partie de l'écart — la
syntaxe de quatre constructions connues. Restent hors de portée :

- **les types de colonnes** : `LONGBLOB` pour les justificatifs en base,
  `deferred=True` sur ces colonnes, la longueur réelle des `VARCHAR`. SQLite
  ignore la plupart de ces contraintes ;
- **le jeu de caractères** : la production est en `utf8mb4` ; un problème
  d'accent, d'emoji ou de collation ne se manifeste pas sur SQLite ;
- **les contraintes et les index** : SQLite n'applique les clés étrangères que si
  on le lui demande explicitement, et se montre plus tolérant sur les
  `UNIQUE` composites ;
- **la latence** : la base est **distante**, chaque requête coûte un aller-retour
  réseau. Un endpoint qui enchaîne les requêtes ou déclenche du lazy-loading est
  instantané en mémoire et lent en production. Aucun test ne le signale ;
- **les migrations sur données réelles** : `test_migration_*.py` les exécute sur
  une SQLite jetable, avec quelques lignes fabriquées. Le volume, les valeurs
  héritées de la version Streamlit et les cas tordus accumulés depuis des années
  ne sont pas là. **Sauvegarder avant toute migration** reste la seule
  protection réelle ;
- **le schéma partagé avec la version legacy Streamlit** : rien ici ne vérifie
  que la legacy continue de fonctionner après une migration.

### En résumé

| La suite couvre | La suite ne couvre pas |
|---|---|
| Logique métier (CRUD, services, workflow) | Le parcours réel dans un navigateur |
| Contrats d'API et permissions par rôle | L'entente réelle front ↔ back (msw simule le back) |
| Le fait qu'un courriel soit demandé | Le fait qu'il arrive |
| La syntaxe SQL face au dialecte MySQL | Le comportement réel sur MariaDB distante |
| Les migrations sur cas fabriqués | Les migrations sur les données de production |
| Le rendu des composants dans jsdom | Le rendu visuel, la caméra, l'impression |
