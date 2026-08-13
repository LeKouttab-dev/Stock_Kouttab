# 06 — Environnements et déploiement

Ce document décrit **où tourne l'application**, **avec quelle configuration**, et
**comment une modification du dépôt arrive en production**. Il ne traite ni
l'architecture applicative, ni le modèle de données, ni le front, ni les tests.

Sources : `compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`,
`DEPLOIEMENT-VPS.md`, `backend/.env.example`, `.env.deploy.example`,
`backend/app/core/config.py`, `backend/scripts/*.py`, et
`.github/workflows/deploy.yml`.

> **Convention de chemins.** Sauf mention contraire, les chemins partent de
> `Gestion_stock_kouttab_react/`, le dossier du projet. Seule exception :
> `.github/workflows/deploy.yml`, qui vit **à la racine du dépôt**, un niveau
> au-dessus — c'est le dépôt entier qui porte le workflow, la version legacy
> Streamlit comprise.

---

## 1. Les trois environnements

| | Développement local | Tests | Production |
|---|---|---|---|
| Où | poste de l'opérateur | poste + CI | VPS IONOS `85.215.168.239`, `/opt/projets/kouttab-stock` |
| Base | SQLite locale ou MySQL O2Switch distante | SQLite **en mémoire** | MySQL/MariaDB **distante**, O2Switch (`sauterelle.o2switch.net:3306`) |
| Exécution | `uvicorn --reload` + `vite dev` | `pytest` | Docker Compose, images GHCR |
| Courriels | selon `EMAIL_ENABLED` | **coupés de force** | activés |
| Domaine | `http://localhost:5173` | — | `https://stock.lekouttab.fr` |
| `APP_ENV` | `development` | non renseigné (donc `development`) | `production` |

`APP_ENV=production` n'est pas décoratif : il arme les garde-fous de
`config.py:127-159` (voir §2.1). En développement, ces contrôles sont
délibérément inactifs — sans quoi il faudrait un secret JWT et une clé de
chiffrement pour lancer l'application sur son poste.

### 1.1 Développement local

**Backend** (`README.md:20-31`) :

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows ; sur Unix : source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # puis remplir
alembic upgrade head
python scripts/create_first_admin_invitation.py prenom.nom@lekouttab.fr
uvicorn app.main:app --reload --port 8000
```

**Frontend**, dans un second terminal :

```bash
cd frontend
npm install
copy .env.example .env                # VITE_API_URL=http://localhost:8000/api/v1
npm run dev                           # http://localhost:5173
```

Le serveur Vite relaie `/api` vers `http://127.0.0.1:8000`
(`frontend/vite.config.ts:29-34`), ce qui permet d'appeler l'API par la
même origine et d'ignorer le CORS. Une variante existe pour tester la caméra
depuis un téléphone du réseau local — `MOBILE=1 npm run dev` sert le front en
HTTPS avec un certificat auto-signé (`vite.config.ts:7-17`) : `getUserMedia` est
réservé aux origines sécurisées, et une page HTTPS ne peut pas appeler une API en
clair.

**La base.** Deux montages coexistent, et c'est une source de confusion réelle :

- `backend/.env.example:7-11` propose la **base MySQL O2Switch
  distante**. Depuis un poste, cela impose d'ajouter l'IP de la box dans
  cPanel → *MySQL distant* — et cette IP change à chaque redémarrage du routeur
  (`DEPLOIEMENT-VPS.md:240-241`).
- Le `.env` réellement présent sur le poste de développement utilise
  `DATABASE_URL=sqlite:///./data/kouttab_local.db`, c'est-à-dire une base SQLite
  sur fichier (`backend/data/kouttab_local.db`). `DATABASE_URL` prend le
  pas sur tous les `DB_*` (`config.py:170-176`), et l'engine adapte son
  paramétrage au SQLite (`backend/app/db/session.py:29-34` : pas de
  `pool_recycle`, `check_same_thread=False`).

Les deux fonctionnent. Travailler sur SQLite évite de dépendre du réseau et de la
liste blanche cPanel ; travailler sur MySQL est le seul moyen de vérifier un
comportement propre au moteur. **Aucun document du dépôt ne tranche entre les
deux** : c'est une information manquante, pas une omission de ce guide.

**Ce qui diffère du reste, en dev :**

- `APP_DEBUG=true` → SQLAlchemy journalise les requêtes (`config.py:29`, via
  `session.py:27`).
- `CORS_ORIGINS` accepte `http://localhost:5173` — impossible en production.
- Les migrations Alembic se jouent à la main, il n'y a pas de conteneur.
- `UPLOAD_DIR=./uploads` et `OUTBOX_DIR=./outbox` sont relatifs au dossier
  `backend/`, et non `/app/...` comme en conteneur.

**Le point de vigilance principal du développement local, c'est le courriel.**
Le `.env` d'exemple pointe sur le **serveur de messagerie réel de
l'association** (`backend/.env.example:25-29`, `config.py:48-53`) : une séance de
tests sur les notes de frais suffit à écrire à de vrais destinataires. Mettre
`EMAIL_ENABLED=false` est le geste attendu — en gardant à l'esprit que depuis le
correctif du 2026-08-13, ce drapeau fait **échouer** l'envoi au lieu de le taire
(§2.2).

### 1.2 Tests

Le socle de test se configure lui-même, **avant tout import applicatif**, dans
`backend/tests/conftest.py` — `settings` est construit à l'import du
premier module de l'application et lirait sinon le `.env` du poste
(`conftest.py:11-16`).

```bash
cd backend
pytest
```

- **Base SQLite en mémoire** : `sqlite:///:memory:` avec `StaticPool`
  (`conftest.py:80-82`), pour que toutes les sessions partagent la même base
  éphémère. Rien n'est écrit sur disque, aucune base réelle n'est jointe.
- **`EMAIL_ENABLED=false` posé en dur** (`conftest.py:28`). Ce n'est pas une
  précaution théorique : la suite a arrosé la boîte de la comptabilité de fausses
  factures (« [Facture] EV(T) — Gala d'été 2026 ») à chaque exécution
  (`conftest.py:18-27`). La fixture d'interception ne couvrait que `_send`, alors
  que le circuit comptable passe par `_send_raw`. Le coupe-circuit est donc armé
  **en amont de tout patch**, pour qu'aucun chemin d'envoi présent ou futur ne
  puisse joindre un vrai serveur. Une seconde barrière existe plus bas dans le
  fichier (`conftest.py:381`).
- **`RIB_ENCRYPTION_KEY` fixe et sans secret** (`conftest.py:34-36`) : sans clé,
  la moindre écriture de RIB lèverait `CleAbsente`. La valeur ne protège rien
  d'autre qu'une base en mémoire.
- **bcrypt à 4 tours au lieu de 12** (`conftest.py:48-56`) : environ dix minutes
  gagnées sur la suite complète. Le hachage reste du vrai bcrypt, seul le facteur
  de travail change.

`APP_ENV` n'est pas positionné : les tests tournent donc hors production, et les
garde-fous de `config.py:127-159` ne s'appliquent pas.

### 1.3 Production

**Cible** : VPS IONOS Ubuntu 24.04, `85.215.168.239`, domaine
`stock.lekouttab.fr` (`DEPLOIEMENT-VPS.md:3-4`). Le projet vit dans
**`/opt/projets/kouttab-stock`** — jamais dans `/opt` directement, et **jamais
dans `/opt/infra`**, qui appartient au socle (`DEPLOIEMENT-VPS.md:175-184`).

**Le VPS est mutualisé.** Il héberge plusieurs projets indépendants, dont
`question.lekouttab.fr`, en production. Le serveur porte sa propre documentation,
`/opt/CLAUDE.md`, qui **fait autorité** (`DEPLOIEMENT-VPS.md:9-17`) :

```bash
ssh <compte>@85.215.168.239 'cat /opt/CLAUDE.md'
```

Architecture à deux étages :

```
   Internet ──443──▶  infra-caddy  ──┬──▶ kouttab-stock-web
                      /opt/infra     ├──▶ kouttab-stock-api
                      ports 80/443   └──▶ kouttab-questions-…
                                          réseau Docker `web`
```

Quatre contraintes en découlent, déjà appliquées dans `compose.yml` :

1. **Aucun `ports:`** (`compose.yml:8-10`). Un unique Caddy détient 80 et 443
   pour toute la machine. Une version antérieure du fichier embarquait son propre
   Caddy publiant ces ports : la déployer telle quelle aurait mis
   `question.lekouttab.fr` hors ligne (`DEPLOIEMENT-VPS.md:35-38`).
2. **Réseau `web` en `external: true`** (`compose.yml:89-94`). Sans cela, Compose
   fabrique un réseau isolé et Caddy ne voit jamais nos conteneurs — symptôme :
   `502 Bad Gateway`.
3. **`container_name` préfixés** (`kouttab-stock-api`, `kouttab-stock-web`,
   `kouttab-stock-outbox`) : Caddy résout les conteneurs par leur nom, deux
   projets nommant leur service `api` entrent en collision.
4. **Jamais de `docker compose down -v` dans `/opt/infra`** : le volume
   `caddy_data` contient les certificats TLS de *tous* les projets
   (`DEPLOIEMENT-VPS.md:44-45`).

**La base reste chez O2Switch**, jointe **en direct**, sans tunnel : l'IP du VPS
est autorisée dans cPanel → *MySQL distant*, et tous les conteneurs sortent avec
cette IP (`compose.yml:21-23`, `DEPLOIEMENT-VPS.md:47-52`). Le service
`db-tunnel` a été retiré du `compose.yml` ; il répondait à un besoin qui n'existe
pas ici.

> **Divergence à connaître** : `DEPLOIEMENT-VPS.md:295-306` et
> `.env.deploy.example:43-53` décrivent encore la variante tunnel
> (`docker compose --profile tunnel up -d db-tunnel`). **Ce service n'existe plus
> dans `compose.yml`** — le dossier `deploy/db-tunnel/` subsiste, mais
> la commande échouerait en l'état. Réactiver le tunnel supposerait de remettre
> le service dans le fichier, puis de le recopier sur le VPS (§5.1).

**Routage et TLS** : notre seule contribution est le fragment
`deploy/site.caddy`, déposé dans `/opt/infra/sites/kouttab-stock.caddy`
et rechargé **à chaud**. Il route `/api/*` et `/health` vers
`kouttab-stock-api:8000`, tout le reste vers `kouttab-stock-web:80`, et pose
HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` et une
`Permissions-Policy` qui autorise la caméra sur notre propre origine
(lecture de codes-barres et scanner de justificatifs).

```bash
# 1. DNS : stock.lekouttab.fr -> 85.215.168.239, VÉRIFIÉ AVANT tout rechargement
nslookup stock.lekouttab.fr

# 2. déposer notre fragment (un fichier à nous, on ne touche pas aux autres)
cp /opt/projets/kouttab-stock/deploy/site.caddy \
   /opt/infra/sites/kouttab-stock.caddy

# 3. recharger À CHAUD — jamais `restart`
cd /opt/infra
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose exec caddy caddy reload   --config /etc/caddy/Caddyfile

# 4. vérifier l'obtention du certificat
docker compose logs --tail 50 caddy | grep -i certificate
```

`docker compose restart caddy` est **interdit** pour cela : un redémarrage coupe
brièvement *tous* les sites de la machine. Et `caddy validate` ne vérifie que la
syntaxe, pas que le routage fonctionne — la seule preuve est une requête réelle
(`DEPLOIEMENT-VPS.md:438-446`).

**Le `.env` de production vit sur le VPS**, à côté de `compose.yml`, en `600`, et
n'est jamais commité ni lu par la CI (`.env.deploy.example:1-6`,
`.github/workflows/deploy.yml:12`). Valeurs attendues, au minimum :

```
APP_ENV=production
APP_DEBUG=false
GHCR_OWNER=<compte-github-en-minuscules>
IMAGE_TAG=<sha du dernier déploiement>       # écrasé à chaque déploiement
DB_HOST=<cluster o2switch>                   # jamais localhost
DB_USER=<prefixe_cpanel>_<user>
DB_NAME=<prefixe_cpanel>_<base>
JWT_SECRET_KEY=<64 octets aléatoires>
RIB_ENCRYPTION_KEY=<base64 de 32 octets>
EMAIL_ENABLED=true
COMPTA_EMAIL=comptabilite@lekouttab.fr
CORS_ORIGINS=https://stock.lekouttab.fr
UPLOAD_DIR=/app/uploads
OUTBOX_DIR=/app/outbox
```

Trois pièges de format, éprouvés sur les autres applications de l'association
(`.env.deploy.example:8-14`, `DEPLOIEMENT-VPS.md:243-254`) : **pas de
guillemets**, **pas d'espace autour du `=`**, **pas de commentaire en fin de
ligne** — `DB_PORT=3306 # port` donne littéralement la valeur `"3306 # port"`, et
l'erreur qui en découle ne ressemble en rien à sa cause. Un mot de passe
contenant `#`, `$` ou une espace se met entre quotes simples.

---

## 2. Le tableau des variables

Deux familles cohabitent dans le même fichier `.env` : celles que **l'application
Python** lit au démarrage (`backend/app/core/config.py`), et celles que **Docker
Compose** substitue dans `compose.yml` au moment du `up`. Une variable Compose
modifiée n'a d'effet qu'après `docker compose up -d` ; une variable applicative
n'a d'effet qu'après redémarrage du conteneur (la configuration est lue une seule
fois, `config.py:191-197`).

### 2.1 Les variables qui décident du démarrage

| Nom | Rôle | Défaut | Si absente ou fausse |
|---|---|---|---|
| `APP_ENV` | `development` \| `production` | `development` (`config.py:20`) | Sur `development` en production, **tous les garde-fous ci-dessous sont désarmés** : secret par défaut, CORS en clair et RIB en clair passent sans un mot. |
| `APP_DEBUG` | Journalisation SQL, traces | `false` (`config.py:21`) | À `true` en production : **refus de démarrage** (`config.py:143-144`). |
| `JWT_SECRET_KEY` | Signature HS256 des jetons | `change-me` (`config.py:42`) | Valeur par défaut (`change-me`, `change-me-in-production`, `secret`, vide) en production : **refus de démarrage** (`config.py:13`, `138-142`). Le défaut est public : signer avec permettrait à quiconque de forger un jeton `Super Admin`. Générer : `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `RIB_ENCRYPTION_KEY` | Chiffrement AES-256-GCM du RIB en colonne | `""` (`config.py:113`) | Vide en production : **refus de démarrage** (`config.py:149-154`). Hors production, toute écriture de RIB lève `CleAbsente`. **La perdre rend les RIB définitivement illisibles** — aucune récupération. Générer : `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. |
| `CORS_ORIGINS` | Origines autorisées, séparées par des virgules | `http://localhost:5173,https://stock.lekouttab.fr` (`config.py:69-72`) | Une origine en `http://` en production : **refus de démarrage** (`config.py:145-146`). |

> **Manque dans le modèle** : `RIB_ENCRYPTION_KEY` **n'apparaît pas** dans
> `.env.deploy.example`, alors que `DEPLOIEMENT-VPS.md:326-328` la déclare
> obligatoire et que son absence empêche le démarrage en production. Un `.env`
> recopié tel quel depuis le modèle produit une API qui ne démarre pas. Même
> constat, sans conséquence de démarrage, pour `DATABASE_URL`, `EMAIL_FROM_NAME`,
> `MAX_ATTACHMENT_TOTAL_MB` et `RATE_LIMIT_ENABLED`.

### 2.2 Courriel

| Nom | Rôle | Défaut | Si absente ou fausse |
|---|---|---|---|
| `EMAIL_ENABLED` | Coupe-circuit d'envoi | `true` (`config.py:53`) | À `false`, **tout envoi échoue et le dit** (`email.py:116-130`). Voir l'encadré ci-dessous. |
| `COMPTA_EMAIL` | Destinataires des pièces comptables, séparés par des virgules | `""` (`config.py:64`) | Vide : les envois **restent en file d'attente sans partir et sans être perdus**, et **sans consommer de tentative** (`outbox.py:212-219`) — sinon la ligne serait abandonnée avant même que l'adresse soit renseignée. C'est arrivé en développement : cinq notes de frais bloquées sans que personne ne le voie (`.env.deploy.example:80-84`). La file repart dès que l'adresse est posée. |
| `SMTP_HOST` | Serveur de messagerie | `localhost` (`config.py:54`) | Vide (ou `SMTP_USER` vide) : aucun client SMTP n'est construit et tout envoi échoue avec « Serveur SMTP non configuré » (`email.py:60-63`, `131-135`). |
| `SMTP_PORT` | Port | `465` (`config.py:55`) | Voir l'incohérence 465/TLS ci-dessous. |
| `SMTP_USER` / `SMTP_PASSWORD` | Authentification | `""` (`config.py:56-57`) | Sans `SMTP_USER`, pas de client SMTP du tout. |
| `SMTP_USE_TLS` | STARTTLS (ports 587/25) | `true` (`config.py:58`) | Corrigé en silence si contredit par le port. |
| `SMTP_USE_SSL` | TLS implicite (port 465) | `false` (`config.py:59`) | Idem. |
| `EMAIL_FROM` / `EMAIL_FROM_NAME` | Expéditeur affiché | `no-reply@lekouttab.fr` / `Le Kouttab Stock` (`config.py:60-61`) | Un expéditeur incohérent avec le compte SMTP se fait généralement rejeter par le serveur. |
| `MAX_ATTACHMENT_TOTAL_MB` | Poids cumulé des pièces jointes par message | `15` (`config.py:84`) | Au-delà, l'envoi est découpé en plusieurs messages plutôt que de faire échouer le dépôt. |

**`EMAIL_ENABLED=false` fait désormais ÉCHOUER l'envoi, et ne se tait plus.**
`_send_raw` retournait auparavant en silence, « pour que le circuit comptable se
déroule jusqu'au bout » — avec pour effet que la file marquait la ligne
« Envoyée ». **La production a tourné ainsi jusqu'au 2026-08-13** : écran des
envois tout en vert, boîtes vides, trois semaines sans aucun signal
(`email.py:103-130`, commit `9630de2`). Ne rien envoyer reste légitime en
développement ; le dire « envoyé » ne l'est jamais. La ligne apparaît maintenant
en échec, avec son motif, et le message rappelle que la configuration est lue au
démarrage : **corriger le `.env` ne suffit pas, il faut redémarrer les
conteneurs**.

**L'incohérence port 465 / TLS, rattrapée en silence.** La configuration livrée
combinait `SMTP_PORT=465` avec `SMTP_USE_TLS=true` et `SMTP_USE_SSL=false`, soit
un STARTTLS sur un port à TLS **implicite**. La connexion échouait, et comme
`_send` avale les exceptions, plus aucun courriel ne partait sans que rien ne le
signale. `_resolve_tls_mode` (`email.py:29-57`) fait donc **primer le port**, qui
est sans ambiguïté :

- port `465` → TLS implicite forcé (`SMTP_USE_SSL=true`, `SMTP_USE_TLS=false`) ;
- ports `587` / `25` → STARTTLS forcé.

L'écart est **journalisé en `warning`**, avec la correction à apporter au `.env`
(`email.py:43-55`). Ce n'est pas une raison de laisser le `.env` faux : le
rattrapage est un filet, pas une configuration. Or le `.env` du poste de
développement porte encore `SMTP_PORT=465` avec `SMTP_USE_TLS=true` et
`SMTP_USE_SSL=false` — exactement la combinaison rattrapée. `.env.deploy.example`
et `backend/.env.example`, eux, sont corrects (`SMTP_USE_TLS=false`,
`SMTP_USE_SSL=true`).

### 2.3 Base de données

| Nom | Rôle | Défaut | Si absente ou fausse |
|---|---|---|---|
| `DATABASE_URL` | URL SQLAlchemy complète | *(aucune)* (`config.py:31`) | **Prend le pas sur tous les `DB_*`** (`config.py:170-176`). C'est le moyen d'activer TLS vers O2Switch (`…?charset=utf8mb4&ssl=true`, `DEPLOIEMENT-VPS.md:292-294`) ou de basculer sur SQLite en local. |
| `DB_HOST` | Nom du **cluster** cPanel | `localhost` (`config.py:26`) | `localhost` en production : la base n'est plus sur la même machine, la connexion échoue en `(2003, Can't connect)`. |
| `DB_PORT` | Port MySQL | `3306` (`config.py:27`) | |
| `DB_USER` / `DB_NAME` | Compte et base, **préfixe cPanel obligatoire** (`abcd1234_monapp`) | `root` / `kouttab_stock` (`config.py:28-30`) | Préfixe oublié : `(1045, Access denied)`. C'est la panne la plus fréquente (`DEPLOIEMENT-VPS.md:249-252`). IP non autorisée dans cPanel : `(1130, … is not allowed to connect)` — le refus arrive **avant** l'authentification. |
| `DB_PASSWORD` | Mot de passe | `""` (`config.py:29`) | |
| `DB_POOL_SIZE` | Taille du pool | `5` (`config.py:37`) | Monter le pool sur un mutualisé fait tomber l'application sur un refus du serveur MySQL (`max_user_connections`). |
| `DB_MAX_OVERFLOW` | Connexions au-delà du pool | `0` (`config.py:38`) | Même raison. |
| `DB_POOL_RECYCLE` | Durée de vie d'une connexion (s) | `280` (`config.py:39`) | Doit rester **sous** le `wait_timeout` du serveur (souvent 300 s), sinon on réutilise des connexions déjà fermées d'en face. |

### 2.4 Fichiers

| Nom | Rôle | Défaut | Si absente ou fausse |
|---|---|---|---|
| `UPLOAD_DIR` | Justificatifs déposés | `./uploads` (`config.py:75`) | En conteneur, **doit valoir `/app/uploads`** : c'est le point de montage du volume `uploads` (`compose.yml:52`) et le dossier créé au bon propriétaire dans l'image (`backend/Dockerfile:52-53`). Une autre valeur écrit dans la couche éphémère du conteneur — tout est perdu au premier redéploiement. |
| `OUTBOX_DIR` | PDF prêts à l'envoi comptable | `./outbox` (`config.py:83`) | **Doit rester HORS de `UPLOAD_DIR`** (`config.py:79-83`) : ces fichiers portent des noms prévisibles (`{Pôle}_{Événement}_{Date}.pdf`), et les servir depuis un dossier exposé rendrait des factures fournisseur téléchargeables sans authentification. En conteneur : `/app/outbox` (`compose.yml:53`). |
| `MAX_UPLOAD_MB` | Taille max par fichier | `10` (`config.py:76`) | |
| `MAX_REQUEST_MB` | Taille max par requête | `50` (`config.py:77`) | |

### 2.5 Divers applicatif

| Nom | Rôle | Défaut |
|---|---|---|
| `JWT_ALGORITHM` | Algorithme de signature | `HS256` (`config.py:43`) |
| `JWT_ACCESS_TOKEN_MINUTES` | Durée du jeton d'accès | `30` (`config.py:44`) |
| `JWT_REFRESH_TOKEN_DAYS` | Durée du jeton de rafraîchissement | `7` (`config.py:45`) |
| `FRONTEND_URL` | Base des liens envoyés par courriel | `http://localhost:5173` (`config.py:67`) |
| `BACKEND_URL` | URL publique de l'API | `http://localhost:8000/api` (`config.py:68`) |
| `RATE_LIMIT_ENABLED` | Limitation de débit `slowapi` | `true` (`config.py:87`) |
| `HELLOASSO_API_BASE`, `HELLOASSO_CLIENT_ID`, `HELLOASSO_CLIENT_SECRET`, `HELLOASSO_ORG_SLUG`, `HELLOASSO_BUVETTE_FORM_SLUG` | Intégration buvette | `config.py:90-101` |
| `HELLOASSO_WEBHOOK_SECRET` | Secret ajouté à l'URL de webhook | `""` (`config.py:106-108`) — vide = **aucune vérification** : HelloAsso ne signe pas ses notifications, n'importe qui peut alors forger des ventes et décrémenter le stock. |

### 2.6 Variables lues par Docker Compose, pas par l'application

| Nom | Rôle | Défaut | Si absente ou fausse |
|---|---|---|---|
| `GHCR_OWNER` | Propriétaire des images GHCR, **en minuscules** | *(aucun)* — déclaré `${GHCR_OWNER:?…}` (`compose.yml:30`) | **Absent : `docker compose` refuse de démarrer** avec « GHCR_OWNER manquant dans .env ». GHCR n'accepte que des noms en minuscules, or un compte GitHub peut porter des majuscules (`deploy.yml:39-42`). |
| `IMAGE_TAG` | Version d'image déployée | `latest` (`compose.yml:30`, `36`) | Épinglé au SHA du commit par le déploiement (`deploy.yml:128`). Laissé à `latest`, on perd la traçabilité et le retour arrière : on ne sait plus quelle version tourne. |
| `OUTBOX_INTERVAL_SECONDS` | Période de la boucle du worker (s) | `600` (`compose.yml:78`) | Substitué **à la création du conteneur** : le modifier impose `docker compose up -d`, un simple `restart` rejouerait l'ancienne commande. |
| `SITE_DOMAIN` | Domaine du site | `stock.lekouttab.fr` (`.env.deploy.example:20`) | **Aucun consommateur dans `compose.yml`.** C'est une *variable GitHub* qu'utilise le contrôle de santé (`deploy.yml:188`). Sa présence dans le `.env` est un vestige. |
| `ACME_EMAIL` | Contact Let's Encrypt | `.env.deploy.example:21` | Vestige : le TLS est géré par le Caddy du socle, pas par ce projet. |
| `O2SWITCH_SSH_HOST`, `O2SWITCH_SSH_USER`, `O2SWITCH_SSH_PORT`, `O2SWITCH_DB_HOST` | Variante tunnel SSH | `.env.deploy.example:50-53` | Vestiges : le service `db-tunnel` n'existe plus dans `compose.yml`. |
| `BACKUP_*` | Ancien service de sauvegarde SFTP | `backend/.env.example:103-115` | Vestiges : le service `backup` a été retiré (`DEPLOIEMENT-VPS.md:470-477`). |

---

## 3. Docker

### 3.1 Les trois services

Fichier : `compose.yml`. Projet Compose nommé `kouttab-stock`
(`compose.yml:28`) — c'est ce nom qui préfixe les volumes.

| Service | Conteneur | Image | Rôle |
|---|---|---|---|
| `web` | `kouttab-stock-web` | `ghcr.io/${GHCR_OWNER}/kouttab-web:${IMAGE_TAG}` | Fichiers statiques du front, servis par nginx. `expose: ["80"]`, jamais publié : seul le Caddy du socle y accède par le réseau `web` (`compose.yml:33-43`). Limite mémoire 128 Mo. |
| `api` | `kouttab-stock-api` | `ghcr.io/${GHCR_OWNER}/kouttab-api:${IMAGE_TAG}` | L'API FastAPI sous uvicorn, `expose: ["8000"]`. Monte les deux volumes, lit `.env` par `env_file` (`compose.yml:45-57`). Limite mémoire 768 Mo. |
| `outbox-worker` | `kouttab-stock-outbox` | **la même image que `api`** | File d'envoi comptable et relances. Remplace le cron cPanel. Pas d'`expose` : il ne sert aucune requête, il dépile la file (`compose.yml:59-83`). Limite mémoire 512 Mo. |

Le worker rejoue en boucle le script d'envoi :

```sh
while true; do
  python scripts/process_outbound_emails.py || true;
  sleep ${OUTBOX_INTERVAL_SECONDS:-600};
done
```

Le `|| true` est délibéré (`compose.yml:73-74`) : un échec SMTP ne doit pas tuer
la boucle, la file gère déjà son propre backoff et reprendra au tour suivant.

**Pourquoi la même image pour l'API et le worker** (`compose.yml:60-63`) : deux
images séparées finiraient par diverger de version, et l'un traiterait la file
avec un code plus ancien que celui qui l'alimente. Une image, deux commandes.

Les trois services portent `restart: unless-stopped` et
`security_opt: no-new-privileges:true`, et **aucun ne publie de port**.

### 3.2 Volumes

```yaml
volumes:
  uploads:      # justificatifs — À SAUVEGARDER (compose.yml:52, 85-87)
  outbox:       # PDF en attente d'envoi comptable (compose.yml:53)
```

Nommés `kouttab-stock_uploads` et `kouttab-stock_outbox` sur le disque du VPS
(préfixe = `name:` du projet). Ils sont montés à l'identique dans `api` et
`outbox-worker` : le worker doit joindre les pièces que l'API a écrites.

**Ce qui doit être sauvegardé — la réponse a changé.** Le commentaire
`# À SAUVEGARDER` de `compose.yml:52` est antérieur à la migration
`f6b3d1e8a295`, qui a fait passer les justificatifs **en base**
(colonnes `contenu` sur `FichiersNotesDeFrais` et `FichiersFactures`), suivie de
`d0f7b2c5e8a9` pour les documents de remboursement. Depuis,
`DEPLOIEMENT-VPS.md:459-468` conclut : **« il n'y a plus rien à sauvegarder
séparément »**, le disque du VPS ne portant plus qu'un cache, que
`files.materialiser` (`backend/app/services/files.py:370-393`) réécrit depuis la
base au besoin.

Nuance à garder en tête : les lignes de la file d'envoi référencent leurs pièces
jointes **par chemin** (`outbox.py:221-225`) ; un fichier absent fait échouer
l'envoi. Perdre le volume `outbox` ne perd donc pas de données comptables, mais
peut faire échouer des envois en attente, à réémettre depuis
*Administration → Envois comptables*. §7 détaille la position à tenir.

### 3.3 Images et construction

**Aucune section `build:` dans `compose.yml`** (`compose.yml:17-19`) : les images
sont construites par GitHub Actions et tirées depuis GHCR. Le VPS n'a donc ni
Node, ni compilateur Python, et **le build ne peut plus le saturer en mémoire** —
c'était le motif du changement.

**Image API** — `backend/Dockerfile`, deux étapes :

- *deps* (`Dockerfile:9-25`) : `python:3.12-slim`, `build-essential` installé
  **dans cette étape seulement**, dépendances dans un venv `/opt/venv`. Si une
  dépendance n'a pas de wheel pour cp312, elle se compile ici et le compilateur
  reste ici.
- *runtime* (`Dockerfile:30-66`) : le venv est copié tel quel ; ni en-têtes de
  compilation ni cache pip ne suivent. Utilisateur non privilégié `kouttab`
  **UID/GID 1001 figés** (`Dockerfile:39-40`) pour que les volumes montés gardent
  le bon propriétaire d'un déploiement à l'autre. `/app/uploads`, `/app/outbox`
  et `/app/logs` sont créés avec le bon propriétaire dans l'image, sinon Docker
  les crée en root au premier démarrage et l'application ne peut plus y écrire
  (`Dockerfile:50-53`). `HEALTHCHECK` en Python pur — curl n'est pas installé,
  surface d'attaque inutile (`Dockerfile:59-61`).
- **Un seul worker uvicorn** (`Dockerfile:63-66`) : la base est distante et le
  mutualisé plafonne `max_user_connections` ; multiplier les workers
  multiplierait les pools et ferait tomber l'application sur un refus MySQL.

**Image Web** — `frontend/Dockerfile` :

- *build* (`Dockerfile:9-27`) : `node:22-alpine`, `npm ci` **avant** la copie du
  source pour que la couche de dépendances soit réutilisée tant que le lockfile
  ne bouge pas. C'est cette étape qui saturait la mémoire du VPS ; elle tourne
  désormais sur un runner GitHub.
- **`VITE_API_URL` est un argument de build, pas une variable d'environnement du
  conteneur** (`Dockerfile:20-25`) : Vite remplace `import.meta.env.VITE_API_URL`
  à la compilation, l'URL est **figée dans le bundle**. La changer impose de
  reconstruire l'image. La CI passe `/api/v1` (`deploy.yml:70`) — chemin relatif,
  puisque le front et l'API partagent l'origine.
- *runtime* : `nginx:1.27-alpine`, `dist/` servi avec le `nginx.conf` du projet.
  Les en-têtes de sécurité et le TLS sont posés par Caddy en amont ; les
  dupliquer les ferait diverger silencieusement. Cache immuable sur `/assets/`
  (noms hachés) et **`no-store` sur `index.html`** : un `index.html` périmé
  pointerait vers des assets supprimés et afficherait une page blanche après
  déploiement.

---

## 4. La chaîne de déploiement

Fichier : `.github/workflows/deploy.yml`. Déclencheurs : `push` sur `main` et
`workflow_dispatch` (`deploy.yml:16-19`).

**Concurrence** (`deploy.yml:23-25`) : groupe `deploy-production`,
`cancel-in-progress: false`. Deux déploiements simultanés se marcheraient dessus,
migrations comprises ; on laisse finir celui qui est en cours plutôt que de
l'interrompre au milieu d'un `alembic upgrade`.

### 4.1 Job `build` — construire et publier

1. **Checkout** (`deploy.yml:37`).
2. **Nom du propriétaire en minuscules** (`deploy.yml:41-42`) :
   `${GITHUB_REPOSITORY_OWNER,,}`. GHCR n'accepte que des noms en minuscules, or
   un compte GitHub peut comporter des majuscules.
3. **Buildx** puis **login GHCR** avec le `GITHUB_TOKEN` du job
   (`deploy.yml:44-50`), sous permission `packages: write`.
4. **Image API** (`deploy.yml:52-61`) : contexte
   `Gestion_stock_kouttab_react/backend`, poussée sous **deux tags** —
   `:${{ github.sha }}` et `:latest`. Cache GitHub Actions en lecture/écriture
   (`type=gha,mode=max`).
5. **Image Web** (`deploy.yml:65-75`) : contexte
   `Gestion_stock_kouttab_react/frontend`, `build-args: VITE_API_URL=/api/v1`,
   mêmes deux tags.
6. **Purge des anciennes versions** (`deploy.yml:81-97`), pour les deux paquets,
   en `min-versions-to-keep: 10`. Le registre conserve une version par
   déploiement et rien ne les supprimait : plusieurs dizaines s'y accumulaient,
   **jusqu'au refus de publication rencontré le 2026-08-12**
   (`denied: permission_denied`). Les dix dernières suffisent largement pour un
   retour arrière. Les deux étapes sont en `continue-on-error: true` — un ménage
   raté ne doit pas bloquer un déploiement.

### 4.2 Job `deploy` — livrer sur le VPS

Environnement GitHub `production` (`deploy.yml:103`), ce qui permet d'y attacher
une approbation manuelle si besoin.

1. **Préparer la connexion SSH** (`deploy.yml:105-112`) : la clé privée
   (`VPS_SSH_KEY`) est écrite en `600`, et **`VPS_KNOWN_HOSTS` est posé**. Sans
   cette empreinte connue à l'avance, on accepterait n'importe quel serveur se
   présentant à cette adresse.

2. **Le script distant** est passé au shell du VPS par l'entrée standard
   (`deploy.yml:117-119`), avec `IMAGE_TAG` positionné à `github.sha`. Il
   s'exécute en `set -euo pipefail` sous le compte `VPS_USER`, dans
   `/opt/projets/kouttab-stock` (`deploy.yml:120-123`). Pas de `sudo` ici : le
   compte de déploiement est propriétaire du `.env` (voir §5.5).

3. **Épingler la version** (`deploy.yml:125-128`) :

   ```bash
   cp .env .env.precedent
   sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${IMAGE_TAG}|" .env
   ```

   Le `.env` précédent est conservé — c'est **tout le mécanisme de retour
   arrière** (§8). Corollaire : `.env.precedent` est écrasé à chaque
   déploiement, on ne remonte donc que d'un cran.

4. **`docker compose pull`** (`deploy.yml:130`) : tire les deux images au tag
   épinglé.

5. **Migrations Alembic** (`deploy.yml:132-141`) :

   ```bash
   docker compose run --rm -T api alembic upgrade head </dev/null
   ```

   Avant le redémarrage, parce que le nouveau code suppose le nouveau schéma.
   Conteneur jetable, l'API tourne encore pendant ce temps. **Le `-T` et le
   `</dev/null` ne sont pas cosmétiques** : voir §5.2.

6. **`docker compose up -d`** (`deploy.yml:143`).

7. **Contrôle que les conteneurs tournent réellement sur la bonne image**
   (`deploy.yml:145-177`) — le point le plus important du workflow :

   ```bash
   for couple in api:api web:web outbox-worker:outbox; do
     service="${couple%%:*}"
     nom="kouttab-stock-${couple##*:}"
     en_place=$(docker inspect --format '{{.Config.Image}}' "$nom" 2>/dev/null || echo absent)
     case "$en_place" in
       *"${IMAGE_TAG}") echo "OK  $nom -> ${IMAGE_TAG}" ;;
       *)
         docker compose up -d --force-recreate "$service"
         # puis re-inspection ; échec définitif => exit 1
         ;;
     esac
   done
   ```

   **Le mode de panne corrigé** : deux déploiements successifs ont laissé les
   anciens conteneurs en place. `up -d` avait rendu la main **sans les
   recréer**, et le workflow se terminait en succès alors que la version livrée
   n'avait pas bougé. Le contrôle porte donc sur le **résultat** — l'image
   réellement chargée par le conteneur, lue par `docker inspect` — et **pas sur
   le code de retour** de la commande. En cas d'écart, il force la recréation,
   revérifie, et échoue franchement si l'écart persiste.

   **`outbox-worker` a été ajouté à cette liste le 2026-08-13**
   (`deploy.yml:152-157`) : il en était absent, si bien qu'il pouvait disparaître
   ou rester sur une vieille image sans que rien ne le signale. Or c'est lui qui
   reprend les envois échoués et déclenche les relances de justificatifs —
   **mort, il ne se voit qu'à l'absence de courriels, des semaines plus tard**.
   Le couple `service:conteneur` est nécessaire parce que les deux noms diffèrent
   pour ce service (`outbox-worker` / `kouttab-stock-outbox`).

8. **Pas de `docker image prune`** (`deploy.yml:179-182`) : voir §5.4.

9. **Contrôle de santé** (`deploy.yml:185-188`), depuis le runner, à travers
   Internet et Caddy :

   ```bash
   curl -fsS --retry 6 --retry-delay 5 --retry-connrefused \
     "https://${{ vars.SITE_DOMAIN }}/api/v1/health"
   ```

   L'endpoint est déclaré sur deux chemins, `/health` et `/api/v1/health`
   (`backend/app/main.py:193-195`), et renvoie `{"status": "ok", "version": …}`.
   **Il ne teste pas la base** : c'est une sonde de disponibilité HTTP, pas un
   diagnostic. Pour la base, l'endpoint dédié est
   `GET /api/v1/admin/database/status` (`backend/app/api/v1/endpoints/admin.py:190`).

**Secrets et variables GitHub attendus** (`deploy.yml:4-10`,
`DEPLOIEMENT-VPS.md:373-386`) :

| Nom | Type | Valeur |
|---|---|---|
| `VPS_HOST` | secret | `85.215.168.239` |
| `VPS_USER` | secret | `deploy` |
| `VPS_SSH_KEY` | secret | clé **privée** ed25519 de déploiement |
| `VPS_KNOWN_HOSTS` | secret | sortie de `ssh-keyscan 85.215.168.239` |
| `SITE_DOMAIN` | variable | `stock.lekouttab.fr` |

**Ce que le workflow ne fait PAS** : il ne copie ni `compose.yml`, ni `deploy/`,
ni le `.env`. Voir §5.1.

---

## 5. Les pièges de production connus

### 5.1 `compose.yml` ne se déploie pas tout seul

Le VPS ne contient **pas de clone du dépôt** : un `git clone` demanderait des
identifiants pour un dépôt privé et donnerait à la machine de production un accès
en lecture à tout l'historique du code — pour trois fichiers
(`DEPLOIEMENT-VPS.md:199-207`). Seuls `compose.yml`, `deploy/` et le `.env` y
vivent, déposés à la main par `scp`.

**Conséquence : le déploiement ne met à jour que les images.** Un service ajouté
au `compose.yml` du dépôt **n'existera pas sur le VPS** tant qu'on ne l'a pas
recopié, et **rien ne le signalera**. C'est la raison pour laquelle les relances
de tickets ont été greffées sur `process_outbound_emails.py` plutôt que confiées
à un conteneur dédié (`backend/scripts/process_outbound_emails.py:74-78`).

La copie se fait **depuis le poste**, via `/tmp` — le dossier du projet n'étant
pas accessible en écriture au compte de connexion (`DEPLOIEMENT-VPS.md:516-521`) :

```bash
# sur le POSTE
scp compose.yml <compte>@85.215.168.239:/tmp/compose.yml.nouveau

# sur le VPS
cd /opt/projets/kouttab-stock
sudo cp /tmp/compose.yml.nouveau compose.yml && sudo chown deploy:deploy compose.yml
sudo docker compose up -d --remove-orphans
```

### 5.2 `docker compose run` sans `-T` avale le reste du script

Le script de déploiement est **transmis au shell distant par l'entrée standard**
(`ssh … bash -s <<'REMOTE'`). `docker compose run` alloue un TTY et **consomme
cette même entrée**, emportant le reste du fichier (`deploy.yml:134-140`).

Le déploiement s'arrêtait donc à la ligne des migrations, **en silence et en
succès** : `docker compose up -d` n'était jamais exécuté, et **la production est
restée trois versions en arrière sans que rien ne le signale** (commit
`78f1c18`). D'où la forme obligatoire :

```bash
docker compose run --rm -T api alembic upgrade head </dev/null
```

`-T` désactive l'allocation du pseudo-TTY, `</dev/null` coupe l'héritage de
l'entrée standard. Les deux, pas l'un ou l'autre. **Toute commande
`docker compose run` ou `exec` ajoutée à ce script doit porter la même
protection.**

### 5.3 `fail2ban` — règle absolue : s'arrêter au premier refus

`fail2ban` surveille le port 22 et **bannit l'adresse IP au bout de quelques
échecs d'authentification**. Le bannissement **survit au redémarrage** : il est
conservé dans `/var/lib/fail2ban/fail2ban.sqlite3` et rejoué au démarrage du
service (`DEPLOIEMENT-VPS.md:69-85`).

**C'est arrivé le 2026-08-11.** Neuf essais successifs pour trouver la bonne clé
ont fermé le port 22 à toute l'adresse IP du bureau — poste de l'opérateur
compris. Le serveur tournait parfaitement, Caddy répondait sur 80 et 443, mais
plus personne ne pouvait s'y connecter, et redémarrer n'y a rien changé.

> **La règle : au premier `Permission denied (publickey)`, on s'arrête et on
> demande.** Essayer une deuxième clé « pour voir » consomme un essai sur le
> compteur. Chercher d'abord quelle clé est censée ouvrir ce serveur — la clé de
> déploiement vit dans le secret GitHub `VPS_SSH_KEY`, pas forcément sur le
> poste.

**Diagnostic** — port 22 muet alors que 80/443 répondent : c'est un bannissement,
pas une panne. `fail2ban` ne filtre que le service concerné.

```bash
for p in 22 80 443; do
  timeout 5 bash -c "echo > /dev/tcp/85.215.168.239/$p" 2>/dev/null \
    && echo "port $p ouvert" || echo "port $p injoignable"
done
```

**Deux portes de sortie, dans cet ordre** (`DEPLOIEMENT-VPS.md:100-113`) :

1. **La console distante IONOS** (panneau → serveur → « Console distante »). Elle
   ne passe pas par le réseau SSH et fonctionne même banni. C'est la seule voie
   fiable.
2. **Une autre adresse IP** (partage de connexion mobile) : le ban porte sur
   l'IP, pas sur le compte.

Puis, une fois connecté — `fail2ban-client` **exige les droits root** :

```bash
sudo fail2ban-client status sshd            # liste les IP bannies
sudo fail2ban-client set sshd unbanip <IP>  # lève le bannissement
```

`root` n'est pas joignable en SSH (`PermitRootLogin no`, c'est voulu) : passer par
un compte sudoer. Et `sudo echo … >> fichier` **n'écrit rien** — la redirection
est exécutée par le shell appelant, qui n'est pas root. Utiliser `| sudo tee -a`.

**Piège associé** (`DEPLOIEMENT-VPS.md:510-514`) : `scp` se lance **depuis le
poste, jamais depuis le VPS**. Lancé dans la session SSH, il tente de joindre le
serveur depuis lui-même avec un compte sans clé : `Permission denied (publickey)`
— et **un échec de plus au compteur `fail2ban`**.

### 5.4 Pas de `docker image prune` sur une machine mutualisée

`docker image prune` agit sur **toute la machine**, qui héberge d'autres projets.
Même filtré sur l'ancienneté, il supprimerait leurs images inutilisées — **et
leur retour arrière avec** (`deploy.yml:179-182`). Le ménage se fait à la main,
en connaissance de cause, en visant des images nommées.

Même logique pour le réseau : `web` est `external: true` (`compose.yml:89-94`) —
`docker compose down` dans notre projet ne doit en aucun cas emporter le réseau
des autres applications.

### 5.5 `sudo` devant toute commande Docker de ce projet

Le `.env` appartient à `deploy` en `600` — c'est voulu, il contient les secrets.
Un autre compte ne peut pas le lire, donc `docker compose` non plus, et la
commande échoue sur un `open … .env: permission denied` qui ne dit pas d'où vient
le problème (`DEPLOIEMENT-VPS.md:505-508`). D'où le `sudo` dans les commandes
d'exploitation ci-dessous — alors que le workflow, qui se connecte **en tant que
`deploy`**, n'en a pas besoin.

Le compte qui pilote Docker doit par ailleurs appartenir au groupe `docker`,
sinon chaque commande répond `permission denied … docker.sock` :

```bash
sudo usermod -aG docker "$USER"    # puis se déconnecter/reconnecter
```

### 5.6 Pas de heredoc Python collé dans un terminal

Le copier-coller ajoute une indentation que Python refuse
(`IndentationError: unexpected indent`), et `<<-` ne supprime que les
tabulations. Écrire la commande **sur une seule ligne**, entre guillemets
**simples**, en n'utilisant que des guillemets doubles à l'intérieur
(`DEPLOIEMENT-VPS.md:523-531`) :

```bash
sudo docker compose exec -T api python -c 'from sqlalchemy import text; from app.db.session import SessionLocal; s=SessionLocal(); print(s.execute(text("SELECT COUNT(*) FROM Admins")).all())'
```

---

## 6. Tâches planifiées

### 6.1 `scripts/process_outbound_emails.py` — file d'envoi, purge, relances

Rejoué en boucle par le service `outbox-worker`, toutes les
`OUTBOX_INTERVAL_SECONDS` secondes (600 par défaut, `compose.yml:75-79`). Ce
service **remplace le cron cPanel** de l'ancienne cible O2Switch, dont la
configuration est encore citée en tête du script
(`process_outbound_emails.py:3-7`).

Trois travaux, dans cet ordre (`process_outbound_emails.py:118-146`) :

1. **Dépiler la file** — `outbox.process_pending(limit=…)`, **20 envois par
   passage** par défaut. Un échec fait repartir la ligne en `failed` avec un
   backoff exponentiel : `5 min × 2^(tentative-1)`, plafonné à 6 h
   (`backend/app/services/outbox.py:36-37, 149`), soit 5, 10, 20, 40 minutes ;
   au bout de `max_attempts` — **5 par défaut**
   (`backend/app/db/models.py:411`) — la ligne passe en `abandoned`
   (`outbox.py:137-138`). Un envoi sans destinataire faute de `COMPTA_EMAIL`
   **ne consomme aucune tentative** et reste `pending`.
2. **Purger les PDF** des envois aboutis depuis plus de **30 jours**
   (`--cleanup-days`, `process_outbound_emails.py:39-67`). Sans cela le disque se
   remplit : chaque justificatif existe en double, l'original dans `uploads/` et
   la copie nommée dans `outbox/`.
3. **Relancer les tickets de justificatif** dont le délai est écoulé
   (`process_outbound_emails.py:70-115`). Cadence portée par
   `crud/ticket.py`. Un bénévole sans adresse ne consomme pas son quota de
   relances : la comptabilité verra le ticket stagner plutôt que de croire
   l'avoir relancé.

**Le script sort toujours en code 0**, même si des envois échouent
(`process_outbound_emails.py:9-12`, `144-146`) : un code d'erreur ferait envoyer
une alerte à chaque exécution, ce qui noierait les vraies anomalies. Les échecs
sont journalisés et visibles dans *Administration → Envois comptables*.

Forcer un passage à la main :

```bash
cd /opt/projets/kouttab-stock
sudo docker compose exec -T api python scripts/process_outbound_emails.py
sudo docker compose logs -f outbox-worker
```

### 6.2 `scripts/relancer_benevoles.py` — relances ponctuelles

**Lancé à la main, jamais planifié** (`relancer_benevoles.py:1-31`).

```bash
cd /opt/projets/kouttab-stock
sudo docker compose exec -T api python scripts/relancer_benevoles.py --rib
```

**Rien ne part sans `--envoyer`** (`relancer_benevoles.py:8-10`, `196-200`). Sans
ce drapeau, le script affiche seulement qui recevrait quoi : écrire à de vraies
personnes ne se déclenche pas par inadvertance, et une liste de destinataires se
relit avant, pas après.

Deux relances, cumulables :

- `--rib` : aux bénévoles dont l'espace ne porte **aucun** relevé d'identité
  bancaire, ni IBAN saisi ni document déposé. Sans RIB, la comptabilité ne peut
  pas virer, et la note reste approuvée sans jamais être payée.
- `--commentaires` : à ceux dont une note porte un commentaire de la comptabilité
  non encore ouvert. Une seule relance par personne, listant toutes ses notes —
  un courriel par note noierait le message chez qui en a plusieurs, et c'est
  précisément celui-là qu'il faut atteindre.

`--utilisateur <identifiant|adresse>` (répétable) restreint à des comptes nommés.
Seuls les comptes `active` pourvus d'une adresse sont considérés ; une faute de
frappe est signalée en `warning` plutôt qu'ignorée — sinon elle se lirait comme
« personne à relancer », donc comme un succès.

Les envois **passent par la file** : ils apparaissent dans *Administration →
Envois comptables*, se relancent d'un clic, et ne se perdent pas si le serveur de
messagerie est indisponible.

---

## 7. Sauvegarde et restauration

### 7.1 Ce qui est sauvegardé

**La base MySQL, par O2Switch**, comme avant la bascule vers le VPS
(`DEPLOIEMENT-VPS.md:64`). C'est la seule sauvegarde automatique du dispositif.

Elle couvre désormais **aussi les pièces comptables**, puisque celles-ci sont
stockées en base :

- justificatifs de notes de frais et de factures — colonnes `contenu`, migration
  `f6b3d1e8a295` (`DEPLOIEMENT-VPS.md:459-464`) ;
- documents de remboursement PDF/XLSX — colonnes `contenu_pdf` / `contenu_xlsx`,
  migration `d0f7b2c5e8a9` ;
- RIB, chiffré en colonne.

Ce choix tient à la mesure : **11 Mo pour l'ensemble des pièces, 4,5 Mo pour la
plus grosse**. Il serait à revoir au-delà de quelques centaines de mégaoctets — la
base est distante, et chaque téléchargement la traverse
(`DEPLOIEMENT-VPS.md:466-468`).

Vérifier qu'aucune pièce n'est restée hors base :

```bash
cd /opt/projets/kouttab-stock
sudo docker compose exec -T api python -c 'from sqlalchemy import text; from app.db.session import SessionLocal; s=SessionLocal(); print(s.execute(text("SELECT COUNT(*), SUM(contenu IS NULL) FROM FichiersFactures")).all())'
```

Le second nombre doit valoir **0**.

### 7.2 Ce qui n'est PAS sauvegardé

- **Les volumes Docker** `kouttab-stock_uploads` et `kouttab-stock_outbox`.
  Aucune sauvegarde ne les couvre : le service `backup` qui les archivait par
  SFTP chez O2Switch **a été retiré** (`DEPLOIEMENT-VPS.md:470-477`), et les
  variables `BACKUP_*` de `backend/.env.example:93-115` sont devenues des
  vestiges. C'est assumé : le disque n'est plus qu'un cache, réécrit depuis la
  base par `files.materialiser` (`backend/app/services/files.py:370-393`).
  Réserve à connaître : les envois **déjà en file** référencent leurs pièces
  jointes par chemin et échouent si le fichier a disparu (`outbox.py:221-225`) ;
  ils sont alors à relancer depuis *Administration → Envois comptables*.
- **Le `.env` du VPS**, qui n'est dans aucune sauvegarde automatique. Il porte
  `RIB_ENCRYPTION_KEY`, dont la perte rend les RIB **définitivement illisibles**
  (`DEPLOIEMENT-VPS.md:350-353`). **En garder une copie hors du serveur**, dans
  un gestionnaire de mots de passe.
- **`compose.yml` et `deploy/` du VPS** — ils existent dans le dépôt, donc rien
  n'est perdu, mais rien ne les restaure automatiquement non plus (§5.1).

> Si un volume doit malgré tout être archivé, le dépôt **ne documente aucune
> procédure** : c'est une information manquante, à décider avant d'en avoir
> besoin.

### 7.3 Avant une migration qui écrit dans les données existantes

Le geste est explicite dans `DEPLOIEMENT-VPS.md:388-413` : **sauvegarder la base
depuis cPanel AVANT toute migration**, puis constater l'état réel plutôt que de le
supposer.

```bash
cd /opt/projets/kouttab-stock
sudo docker compose pull

# 1. Sauvegarde de la base depuis cPanel — non négociable.
# 2. Constater où l'on en est :
sudo docker compose run --rm -T api alembic current </dev/null
#    - une révision s'affiche          -> passer directement à `upgrade head`
#    - rien, mais les tables existent  -> schéma hérité du legacy Streamlit :
sudo docker compose run --rm -T api alembic stamp <revision_deja_appliquee> </dev/null
# 3. Appliquer le reste :
sudo docker compose run --rm -T api alembic upgrade head </dev/null

sudo docker compose up -d
sudo docker compose ps          # les 3 services doivent être "running"
```

**Ne jamais lancer `alembic upgrade head` sans avoir regardé `alembic current`.**
Rejouer une migration initiale sur un schéma déjà en place échoue au mieux, et
laisse la base à moitié migrée au pire.

**Cas d'école — la migration `a1c8e6f2b307` (chiffrement des RIB).** L'ordre des
opérations n'est pas négociable (`DEPLOIEMENT-VPS.md:342-348`) :

1. `RIB_ENCRYPTION_KEY` est dans le `.env` **avant** le déploiement ;
2. la migration chiffre les RIB déjà enregistrés — **sans clé, elle s'arrête et
   ne convertit rien**, plutôt que de laisser une base à moitié chiffrée ;
3. l'API démarre et lit les RIB comme avant, chiffrement compris.

Vérification après coup :

```bash
sudo docker compose exec -T api python -c 'from sqlalchemy import text; from app.db.session import SessionLocal; s=SessionLocal(); r=s.execute(text("SELECT rib FROM Admins WHERE rib IS NOT NULL AND rib <> \"\"")).scalars().all(); print(len(r), "RIB,", len([x for x in r if not x.startswith("gcm1:")]), "en clair")'
```

`0 en clair` est le résultat attendu.

---

## 8. Retour arrière

Chaque déploiement **épingle un tag d'image** dans le `.env` et **conserve le
`.env` précédent** (`deploy.yml:125-128`). Le retour arrière consiste donc à
restaurer ce fichier (`DEPLOIEMENT-VPS.md:487-499`) :

```bash
cd /opt/projets/kouttab-stock
sudo cp .env.precedent .env         # restaure l'IMAGE_TAG d'avant
sudo docker compose up -d
sudo docker compose ps
```

Puis vérifier que les conteneurs tournent bien sur l'ancienne image — le même
contrôle que le workflow, pour la même raison (`up -d` peut rendre la main sans
recréer) :

```bash
for nom in kouttab-stock-api kouttab-stock-web kouttab-stock-outbox; do
  echo "$nom : $(sudo docker inspect --format '{{.Config.Image}}' "$nom")"
done
curl -fsS https://stock.lekouttab.fr/api/v1/health
```

**Trois limites à connaître :**

1. **On ne remonte que d'un cran.** `.env.precedent` est écrasé à chaque
   déploiement. Pour remonter plus loin, éditer `IMAGE_TAG` à la main avec le SHA
   voulu — les **dix dernières** versions seulement sont conservées sur GHCR
   (`deploy.yml:81-97`).
2. **Une migration Alembic ne se défait pas toute seule.** Si le déploiement a
   migré le schéma, restaurer aussi la sauvegarde de base prise avant la
   migration. **C'est la raison pour laquelle cette sauvegarde est obligatoire**
   (`DEPLOIEMENT-VPS.md:496-499`).
3. **`compose.yml` ne revient pas en arrière tout seul** (§5.1). Si le
   déploiement fautif s'accompagnait d'une modification de `compose.yml` recopiée
   à la main, il faut aussi remettre l'ancienne version, par la même voie.

### Exploitation courante

```bash
cd /opt/projets/kouttab-stock
sudo docker compose ps                     # état des services
sudo docker compose logs -f api            # journaux de l'API
sudo docker compose logs -f outbox-worker  # file d'envoi et relances
sudo docker compose restart api            # redémarrage ciblé
cd /opt/infra && sudo docker compose logs --tail=50 caddy   # TLS, accès
```

---

## Informations manquantes, relevées à la rédaction

- Le dépôt **ne tranche pas** entre SQLite locale et MySQL O2Switch pour le
  développement (§1.1) ; les deux montages coexistent.
- **`RIB_ENCRYPTION_KEY` est absente de `.env.deploy.example`** alors qu'elle est
  obligatoire en production (§2.1).
- La variante **tunnel SSH** est encore documentée et paramétrée, mais le service
  `db-tunnel` **n'existe plus** dans `compose.yml` (§1.3).
- **Aucune procédure de sauvegarde des volumes Docker** n'est documentée depuis
  le retrait du service `backup` (§7.2).
- Le nom du compte de connexion au VPS est écrit tantôt `deploy`, tantôt
  `<compte>` selon les passages de `DEPLOIEMENT-VPS.md` ; seul le secret GitHub
  `VPS_USER` fait foi.
- Le commentaire `# À SAUVEGARDER` de `compose.yml:52` **contredit**
  `DEPLOIEMENT-VPS.md:459-461` depuis la migration `f6b3d1e8a295` (§3.2).
