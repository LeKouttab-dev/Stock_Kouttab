# 05 — Sécurité

Ce document décrit les protections **effectivement en place** dans Kouttab Stock
React : ce qu'elles font, et surtout **pourquoi** elles existent. La plupart des
commentaires du code racontent l'incident qui les a motivées — ils sont repris
ici plutôt que reformulés.

Périmètre : authentification, autorisation, données sensibles, dépôts de
fichiers, configuration de production, webhook HelloAsso, CORS et en-têtes.
L'architecture, le modèle de données, le déploiement et les tests sont traités
ailleurs.

---

## 1. Authentification

### 1.1 Jetons JWT

Deux jetons distincts, signés avec la même clé (`JWT_SECRET_KEY`) et le même
algorithme (`HS256` par défaut, `config.py:43`).

| Jeton | Durée | Réglage | Contenu |
|---|---|---|---|
| Accès | 30 min | `JWT_ACCESS_TOKEN_MINUTES` (`config.py:44`) | `sub`, `role`, `type: "access"`, `iat`, `exp` |
| Rafraîchissement | 7 jours | `JWT_REFRESH_TOKEN_DAYS` (`config.py:45`) | `sub`, `type: "refresh"`, `jti`, `iat`, `exp` |

- `create_access_token` (`security.py:69-86`) place le **rôle dans le jeton**,
  ce qui évite une lecture en base pour la plupart des vérifications — mais
  `get_current_user` relit malgré tout le compte (§2).
- `decode_token` (`security.py:114-126`) distingue deux échecs : `TOKEN_EXPIRED`
  quand la date `exp` est dépassée, `TOKEN_INVALID` pour tout le reste
  (signature, format). Le front s'appuie sur cette distinction pour déclencher
  un rafraîchissement silencieux plutôt qu'une déconnexion.
- Le champ `type` est vérifié à l'usage : `deps.py:27-28` refuse un jeton de
  rafraîchissement présenté comme jeton d'accès, et `auth.py:323-326` refuse
  l'inverse. Sans ce contrôle, le jeton de 7 jours ferait office de jeton
  d'accès permanent.

### 1.2 Rotation du jeton de rafraîchissement

`create_refresh_token` (`security.py:89-106`) tire un `jti` avec
`secrets.token_urlsafe(32)` et le retourne à part. Le commentaire est explicite :

> Le `jti` identifie le token de manière unique et permet de le révoquer côté
> base : sans lui, un refresh token volé restait utilisable jusqu'à son
> expiration naturelle.

Seul le **SHA-256 du `jti`** est stocké (`security.py:109-111`, colonne
`RefreshTokens.jti_hash`, `models.py:245`) : une fuite de la base ne permet pas
de rejouer les jetons.

`POST /auth/refresh` (`auth.py:315-352`) échange l'ancien couple contre un couple
neuf. `consume_refresh_token` (`auth_security.py:144-170`) porte la règle
essentielle — **la détection de rejeu** :

> Si le token a déjà été tourné, c'est qu'il circule en double — on révoque
> alors toute la famille du compte plutôt que de laisser coexister la session
> légitime et celle du voleur.

Un jeton émis avant l'introduction de la rotation (donc sans `jti`) est refusé
volontairement (`auth.py:332-339`) : « on le refuse pour forcer une reconnexion
propre plutôt que de laisser un trou ».

`POST /auth/logout` (`auth.py:358-375`) révoque le jeton fourni, ou **toutes les
sessions** du compte à défaut. La table `RefreshToken` (`models.py:230-...`)
existe précisément pour cela : sans elle, « `/auth/logout` ne pouvait rien
révoquer et un refresh token volé restait valide sept jours ».

`POST /auth/reset-password` (`auth.py:221-239`) appelle `revoke_all_for_user` :
si la demande fait suite à une compromission, laisser vivre les jetons existants
rendrait la réinitialisation inutile.

Côté client, les jetons sont conservés par le store Zustand persisté
(`frontend/src/stores/auth.ts:17-37`), donc en `localStorage`. L'intercepteur
Axios (`frontend/src/api/client.ts:39-116`) rejoue une requête après un 401 ou un
`AUTH_1010`, en sérialisant les rafraîchissements concurrents dans une file.

### 1.3 Mots de passe

- **bcrypt, coût 12** (`security.py:27-30`). `_bcrypt_safe` (`security.py:19-22`)
  tronque à 72 octets, la limite dure de bcrypt.
- **Hachages hérités** : la version Streamlit stockait du SHA-256 nu.
  `is_legacy_hash` (`security.py:56-60`) les reconnaît à leur forme (64
  caractères hexadécimaux) et `verify_password_legacy` (`security.py:43-53`) les
  vérifie. Un login réussi sur un hachage hérité renvoie
  `password_must_change=True` (`auth.py:292-296`), ce qui force le
  renouvellement côté application.
- **Règles de robustesse** (`validate_password_strength`, `security.py:136-148`) :
  8 caractères minimum, au moins une majuscule, une minuscule, un chiffre et un
  caractère spécial. Appliquées à l'inscription (`auth.py:94-96`), à la création
  du Super Admin par invitation (`auth.py:426-428`) et à la réinitialisation
  (`crud/password_reset.py`).
- **Identifiant** : `^[A-Za-z0-9_]{3,20}$` (`security.py:131`, `151-154`).

### 1.4 Limitation de débit

Le limiteur `slowapi` est isolé dans `core/rate_limit.py:23-26`. Son
emplacement n'est pas cosmétique — l'en-tête du module raconte le défaut
corrigé :

> Le `Limiter` vivait dans `app.main`, où les routers ne pouvaient pas
> l'importer sans créer un cycle. C'est la raison pour laquelle **aucun endpoint
> n'était effectivement limité** malgré le middleware en place.

Limites en vigueur (`api/v1/endpoints/auth.py`) :

| Endpoint | Limite | Ligne |
|---|---|---|
| `POST /auth/signup` | 3 / heure | `auth.py:85` |
| `POST /auth/login` et `/auth/login/json` | 10 / 15 min | `auth.py:246`, `auth.py:259` |
| `POST /auth/forgot-password` | 5 / heure | `auth.py:144` |
| `POST /auth/reset-password` | 10 / heure | `auth.py:222` |
| `GET /auth/validate-invitation` | 10 / heure | `auth.py:390` |
| `POST /auth/admin-setup` | 5 / heure | `auth.py:402` |

La clé est l'adresse IP (`get_remote_address`). Le compteur est **en mémoire de
process** (`rate_limit.py:8-12`) : avec plusieurs workers, la limite réelle est
un multiple de celle annoncée. C'est assumé — « acceptable pour freiner un
bruteforce, mais ce n'est pas une garantie stricte ». Un backend Redis serait
nécessaire, indisponible sur l'hébergement mutualisé d'origine.

La réponse 429 est réécrite (`main.py:96-113`) pour suivre l'enveloppe
`{code, message, extras}` du reste de l'API, avec un code distinct sur
`/auth/login`.

`RATE_LIMIT_ENABLED` (`config.py:87`) permet de couper le limiteur — utile en
tests.

### 1.5 Verrouillage après échecs

Complémentaire de la limitation de débit, et persisté en base
(`crud/auth_security.py`) :

- **5 échecs** (`LOCKOUT_THRESHOLD`, `auth_security.py:25`) déclenchent un
  verrou de **15 minutes** (`LOCKOUT_WINDOW`, `auth_security.py:26`).
- Un compteur inactif depuis 24 h repart de zéro (`ATTEMPT_TTL`,
  `auth_security.py:28`), et `purge_stale_attempts` (`auth_security.py:119-124`)
  fait le ménage.
- `_do_login` (`auth.py:269-309`) interroge `is_locked` **avant** toute
  vérification de mot de passe, et enregistre un échec aussi bien pour un compte
  inexistant que pour un mot de passe faux — sans quoi le temps de réponse
  distinguerait les deux cas.

La clé du compteur est le couple **(identifiant, IP)** (`models.py:201-217`), et
le commentaire dit pourquoi :

> Verrouiller sur le seul username permettait à un tiers de bloquer n'importe
> quel compte en cinq requêtes.

L'historique du choix figure aussi dans le modèle : le verrouillage était
auparavant un dictionnaire en mémoire, « il disparaissait à chaque redémarrage
Passenger, n'était pas partagé entre workers, et grossissait sans borne ».

### 1.6 Invitations et réinitialisation

- **Invitations** (`crud/invitation.py`) : jeton `secrets.token_urlsafe(32)`,
  stocké en SHA-256 (`security.py:165-167`), expiration 24 h
  (`TOKEN_TTL_HOURS`, `invitation.py:18`), 3 tentatives de validation au maximum
  (`MAX_VALIDATION_ATTEMPTS`, `invitation.py:19`), usage unique (`used`).
- **Mot de passe oublié** (`crud/password_reset.py`) : jeton haché, validité
  **1 heure** (`DUREE_VALIDITE`, `password_reset.py:29`) — « assez pour relever
  ses courriels, trop court pour qu'un lien oublié dans une boîte partagée reste
  exploitable longtemps ». Émettre un jeton **invalide les précédents** du même
  compte (`password_reset.py:36-62`).
- `POST /auth/forgot-password` (`auth.py:143-196`) renvoie **la même réponse dans
  tous les cas** :

  > Répondre « compte inconnu » transformerait cet endpoint en oracle :
  > n'importe qui pourrait vérifier si une adresse est enregistrée dans
  > l'association.

  Même logique pour l'envoi, encapsulé dans `_send_reset_safe`
  (`auth.py:199-206`) : « un envoi raté ne doit pas révéler l'existence du compte
  par une 500 ». Un compte non `active` ne peut pas se donner un mot de passe
  (`auth.py:176-180`).

---

## 2. Autorisation

### 2.1 Les deux briques

**`get_current_user`** (`deps.py:22-41`) décode le jeton, vérifie son `type`,
relit le compte en base et refuse les comptes `rejected` ou non `active`. La
relecture en base n'est pas redondante : un compte désactivé après l'émission du
jeton est bloqué immédiatement, sans attendre les 30 minutes d'expiration.

**`require_roles(*roles)`** (`deps.py:44-56`) fabrique une dépendance FastAPI qui
compare `current_user.role` à l'ensemble autorisé et lève `ROLE_REQUIRED` en
exposant les rôles attendus.

Côté navigateur, `frontend/src/lib/auth.ts` porte la matrice `PERMISSIONS` et la
fonction `canAccess`. C'est un **confort d'affichage, pas un contrôle** : elle
masque des boutons, le serveur décide. Plusieurs entrées portent d'ailleurs la
consigne explicite de rester alignées sur le back (`auth.ts:59`, `auth.ts:64-65`,
`auth.ts:69-70`, `auth.ts:72-73`).

### 2.2 Le principe : le rôle **et** la propriété

Le contrôle par rôle seul ne suffit jamais sur les objets qui appartiennent à
quelqu'un. La raison est écrite noir sur blanc dans `users.py:150-155` :

> Le contrôle porte sur le rôle **et** sur la propriété : un bénévole qui devine
> l'identifiant d'un collègue ne doit pas récupérer ses coordonnées bancaires.

Les identifiants sont des **entiers auto-incrémentés qui se suivent** : `…/42`
puis `…/43` est une énumération triviale. Un endpoint qui vérifie seulement
« l'appelant est authentifié » est donc, en pratique, un endpoint ouvert à tous
les utilisateurs de l'application.

Exemples réels dans le code :

**RIB (`users.py`)** — `_peut_voir_le_rib` (`users.py:97-98`) :

```python
return demandeur.role in ("Compta", "Super Admin") or demandeur.id == proprietaire_id
```

Appliqué au téléchargement du document (`users.py:144-161`). L'annuaire
(`users.py:38-54`), ouvert à la Compta et au Super Admin, sert `UserOut` et
**non** `UserDetailOut` : « cet écran est un annuaire, pas un fichier de
coordonnées bancaires ».

**Justificatif de remboursement (`reimbursements.py:114-139`)** — le bénévole
concerné y a droit, « c'est la preuve de son remboursement », mais uniquement le
sien :

```python
if current_user.role not in _ACCOUNTANT_ROLES and row.id_user != current_user.id:
    raise AppException(ErrorCode.FORBIDDEN)
```

La même règle borne la liste (`reimbursements.py:73-87`) : tout pour la
comptabilité, ses propres versements pour les autres.

**Fichiers de note de frais (`expenses.py`)** — listage
(`expenses.py:432-444`) et téléchargement (`expenses.py:525-542`) répètent le
même test :

```python
if expense.id_user != current_user.id and current_user.role not in _ACCOUNTANT_ROLES:
    raise AppException(ErrorCode.FORBIDDEN, detail="Acces refuse a ce fichier.")
```

Le téléchargement vérifie en plus que le fichier appartient bien à la note
demandée (`expenses.py:540`) — sinon l'identifiant de note ne servirait à rien et
un fichier quelconque serait accessible depuis n'importe quelle note dont on est
propriétaire. Les factures appliquent le même contrôle
(`invoices.py:328-330`).

**RIB dans la liste des notes** — `_to_out` (`expenses.py:69-80`) efface
`user_rib` et `user_rib_document_nom` de la réponse quand `_can_see_rib` dit non.
Le filtrage se fait à la sérialisation, pas dans la requête : un oubli côté
écran n'expose donc rien.

L'ajout d'une pièce à une note existante passe par
`peut_deposer_une_piece` (`crud/expense.py:490`), qui combine propriété et état
de la note (`expenses.py:473-480`).

---

## 3. Données sensibles

### 3.1 `Admins.rib` chiffré au repos

La colonne est déclarée `ChampChiffre(255)` (`models.py:108`). Le chiffrement
n'est **pas** dans le CRUD mais dans le type de colonne
(`db/types.py:23-54`), et c'est délibéré :

> `ChampChiffre` place le chiffrement à la frontière de la base plutôt que dans
> le CRUD : tout ce qui lit ou écrit `Admin.rib` passe par lui, y compris le
> code écrit plus tard qui ignorerait tout du sujet. Un chiffrement qu'on peut
> oublier d'appeler finit toujours par être oublié quelque part.

L'algorithme est **AES-256-GCM** (`core/crypto.py`), en mode authentifié : « une
valeur modifiée directement en base est refusée au lieu de produire un faux RIB
en silence ». Nonce de 12 octets tiré à chaque écriture (`crypto.py:46`,
`crypto.py:142`), clé de 32 octets en base64 (`crypto.py:104-112`).

La menace visée est explicite (`crypto.py:1-8`) : les permissions applicatives
« ne protègent rien contre ce qui contourne l'application : un export de la base,
une sauvegarde égarée, un accès MySQL direct. Les coordonnées bancaires de tous
les bénévoles tenaient dans un `SELECT` ».

**Format stocké** : `gcm1:<base64(nonce || chiffré || tag)>` (`crypto.py:45`).
Le préfixe sert deux fois (`crypto.py:15-18`) : il versionne le schéma — un
`gcm2` futur sera introduit sans ambiguïté — et il **distingue une valeur
chiffrée d'un RIB en clair hérité**.

**Compatibilité avec l'existant** : `dechiffrer` (`crypto.py:147-158`) rend
telle quelle toute valeur sans préfixe. Sans cela, « toute la page des notes de
frais tomberait au premier déploiement, avant même qu'un seul RIB ait été
converti ». Symétriquement, `chiffrer` (`crypto.py:131-144`) laisse passer
`None` et la chaîne vide, et ne re-chiffre pas une valeur déjà chiffrée.

**Une valeur illisible ne fait pas tomber la requête** : `process_result_value`
(`db/types.py:40-54`) journalise et renvoie `None`. « Le contraire rendrait toute
la page inaccessible pour un seul compte abîmé, alors que la comptabilité a
besoin des autres. »

**La clé est irremplaçable.** `RIB_ENCRYPTION_KEY` (`config.py:110-113`) :

> La perdre rend les RIB déjà enregistrés **définitivement illisibles** : elle se
> sauvegarde avec le reste du `.env`, hors du dépôt.

Il n'existe aucune procédure de récupération. La seule sortie serait de
redemander leur RIB à tous les bénévoles.

**Pas de données associées (AAD)** liant le chiffré à son propriétaire
(`crypto.py:20-25`) : le `TypeDecorator` ne connaît pas l'identifiant de la
ligne. Déplacer un RIB d'un compte à l'autre directement en base resterait donc
possible pour qui a déjà les droits d'écriture MySQL — un adversaire « nettement
plus avancé que celui visé ici, et qui pourrait de toute façon changer l'IBAN
affiché à la comptabilité ».

### 3.2 Le RIB en document : non chiffré, et pourquoi

`Admins.rib_document` est un BLOB stocké en base, `deferred`
(`models.py:116-123`). Le commentaire porte l'arbitrage :

> Le contenu n'est pas chiffré, contrairement à `rib` : un BLOB traverserait mal
> `ChampChiffre`, conçu pour du texte, et **la protection utile ici est le
> contrôle d'accès**.

Trois éléments complètent ce choix :

1. **Aucune copie disque.** Le dépôt passe par `lire_en_memoire`
   (`users.py:118`, `services/files.py:259-295`), qui valide sans jamais écrire —
   « une copie de plus d'une donnée bancaire est une surface de fuite de plus ».
2. **Rien ne l'envoie par courriel**, donc rien n'a besoin d'un chemin sur
   disque, contrairement aux justificatifs comptables.
3. **L'accès est le même que celui de l'IBAN** : propriétaire, Compta, Super
   Admin (`users.py:97-98`).

Le chiffrement du champ texte protège contre une fuite du contenu de la base ; le
document, lui, reste protégé par le seul contrôle d'accès applicatif. C'est un
écart de protection assumé entre deux formes de la même donnée (voir
§8).

---

## 4. Dépôts de fichiers

Tout passe par `app/services/files.py`.

### 4.1 Validation par la signature du contenu

`_detect_mime` (`files.py:65-84`) déduit le type réel des premiers octets —
**jamais de l'extension, jamais de l'en-tête `Content-Type` du client**. La table
`_MAGIC` (`files.py:55-59`) couvre PNG, JPEG et PDF ; deux formats demandent un
traitement à part :

- **HEIC** est une boîte ISO-BMFF : `ftyp` aux octets 4-8, la marque aux octets
  8-12 (`_MARQUES_HEIF`, `files.py:62` : `heic`, `heix`, `heim`, `heis`, `hevc`,
  `mif1`, `msf1`). Une entrée de plus dans `_MAGIC` ne l'aurait pas attrapé.
- **WEBP** exige `RIFF` en 0-4 **et** `WEBP` en 8-12 — « tester `RIFF` seul
  accepterait un WAV ou un AVI ».

HEIC compte : c'est le format par défaut d'iOS dès qu'on dépose depuis
« Fichiers » plutôt que depuis la photothèque. Il était refusé avec
« Extension 'heic' non autorisée », « de la prose de développeur servie à un
bénévole, pour le geste le plus courant de l'application » (`files.py:29-32`).

**Aucun repli sur le MIME client** (`files.py:118-120`) :

> Il est fourni par le client et se falsifie trivialement. Un fichier arbitraire
> renommé en `.jpg` avec un en-tête `Content-Type: image/jpeg` était accepté tel
> quel.

`validate_file_type` (`files.py:97-150`) applique donc trois filtres successifs :
extension dans la liste blanche du sous-dossier, signature reconnue, signature
compatible avec le sous-dossier. L'extension enregistrée est **canonique**,
dérivée du type détecté (`files.py:149`) et non de ce qu'a envoyé le client.

### 4.2 Formats acceptés

`EXTENSIONS_ALLOWED` (`files.py:43-52`) — identique pour les trois usages :

| Sous-dossier | Extensions |
|---|---|
| `expenses` | `png`, `jpg`, `jpeg`, `pdf`, `webp`, `heic`, `heif` |
| `invoices` | idem |
| `rib` | idem |

WEBP avait été retiré faute d'extension correspondante, ce qui produisait
l'incohérence inverse : « un fichier renommé en `.jpg` passait la validation puis
était stocké en `.webp`, hors du jeu autorisé » (`files.py:25-28`). Le PDF est
accepté sur les tickets de caisse depuis que le scanner intégré rend un PDF prêt
à partir (`files.py:44-46`).

### 4.3 Limites de taille

- **Par fichier** : `MAX_UPLOAD_MB`, 10 Mo par défaut (`config.py:76`). Le
  contrôle se fait **pendant l'écriture par morceaux** (`files.py:199-219`) : le
  fichier partiel est supprimé dès le dépassement, sans jamais charger l'ensemble
  en mémoire. `lire_en_memoire` lit `max + 1` octet et rejette au-delà
  (`files.py:274-280`).
- **Par requête** : `MAX_REQUEST_MB`, 50 Mo (`config.py:77`), appliqué par un
  middleware sur l'en-tête `Content-Length` (`main.py:121-138`). Ce réglage
  « était déclaré dans la configuration mais n'était lu nulle part : la limite
  n'existait pas ». Le Caddyfile fixe le même plafond côté proxy, volontairement
  identique : « un plafond plus bas ici renverrait un 413 que l'application ne
  verrait jamais, donc sans message exploitable ».
- **Pièces jointes de courriel** : `MAX_ATTACHMENT_TOTAL_MB`, 15 Mo
  (`config.py:84`).

### 4.4 Confinement des chemins

`_is_inside_uploads` (`files.py:298-310`) résout le chemin candidat et vérifie
qu'il est bien sous `UPLOAD_DIR`. La justification est précise :

> `chemin_fichier` provient de la base, mais **la base n'est pas une source de
> confiance** : `POST /admin/database/import` insère des lignes depuis un CSV
> fourni par l'utilisateur. Sans ce contrôle, un chemin arbitraire
> (`/home/user/backend/.env`) était servi tel quel par `FileResponse`.

Le garde s'applique à la lecture (`get_file_path`, `files.py:328-335`) comme à la
suppression (`delete_file`, `files.py:313-326`), les deux journalisant le refus.

Les noms de fichiers sont réécrits en `uuid4().hex` (`files.py:196`) et rangés
par année/mois (`files.py:157-161`) : le nom d'origine n'atteint jamais le
système de fichiers.

Un point voisin : `OUTBOX_DIR` est **volontairement hors de `UPLOAD_DIR`**
(`config.py:79-83`), parce que les PDF prêts à l'envoi portent des noms
prévisibles (`{Pôle}_{Événement}_{Date}.pdf`) et que le `.htaccess` laisse passer
`/backend/uploads/` — « les y écrire rendrait des factures fournisseur
téléchargeables sans authentification ».

### 4.5 Conversion systématique en PDF

Tout justificatif est enregistré sous forme de PDF
(`save_upload_file(..., convertir_en_pdf=True)`, `files.py:231-247`, appelé
notamment en `expenses.py:485`). Motif (`files.py:169-176`) : le PDF n'existait
que dans `OUTBOX_DIR` pour la pièce jointe du courriel, purgé à 30 jours ; ce qui
restait en base et se retéléchargeait depuis l'application était l'image
d'origine, d'où un écart visible avec le scanner.

La conversion ne dégrade rien : `img2pdf` embarque le flux JPEG tel quel, sans
ré-encodage (`services/pdf.py:1-7`). Un PDF déposé reste identique octet pour
octet. Le gabarit est forcé en A4 (`pdf.py:44-49`) : sans contrainte explicite,
les photos de smartphone sans DPI déclarés produisaient « des pages de plusieurs
mètres, illisibles à l'impression ». `pillow-heif` est enregistré à l'import
(`pdf.py:24-33`), sans quoi Pillow refuse tout HEIC.

Le fichier disque suit le contenu converti (`files.py:236-247`) pour ne pas
laisser une ligne dont `type_fichier` annonce un PDF pointer vers une image.
La conversion **n'est pas rétroactive** : les pièces antérieures restent des
images et restent lisibles.

---

## 5. Refus de démarrage en production

`_refuse_insecure_production_config` (`config.py:127-159`) est un validateur
Pydantic exécuté à la construction des réglages. Il ne fait rien hors production
(`config.py:135`, `is_production` = `APP_ENV == "production"`). Le principe :

> Le défaut `change-me` est public : signer les JWT avec permettrait à n'importe
> qui de forger un token `Super Admin`. **Mieux vaut un refus de démarrage
> bruyant qu'une application ouverte silencieusement.**

Quatre contrôles, cumulés en une seule erreur listant tous les problèmes :

| Contrôle | Ligne | Pourquoi |
|---|---|---|
| `JWT_SECRET_KEY` hors de `INSECURE_JWT_SECRETS` (`change-me`, `change-me-in-production`, `secret`, vide) | `config.py:13`, `138-142` | Une clé publique = forge de jetons Super Admin |
| `APP_DEBUG` à `false` | `config.py:143-144` | Traces d'exception exposées |
| Aucune origine CORS en `http://` | `config.py:145-146` | Jeton transporté en clair |
| `RIB_ENCRYPTION_KEY` non vide | `config.py:147-154` | « Sans clé, les RIB repartiraient en clair dans la base sans que rien ne le signale — exactement la situation que le chiffrement corrige » |

Les messages d'erreur donnent la commande de génération de chaque clé
(`config.py:140-141`, `config.py:152-153`).

Effet de bord voulu : `is_production` désactive aussi `/docs`, `/redoc` et
`/openapi.json` (`main.py:67-79`) — « la documentation interactive décrit toute
la surface d'API (endpoints admin, schémas, codes d'erreur) ».

### Le cas `EMAIL_ENABLED` : signalé, pas bloquant

`EMAIL_ENABLED=false` **n'empêche pas le démarrage**. Au lancement, `lifespan`
émet un avertissement explicite (`main.py:51-60`) :

> `EMAIL_ENABLED=false` — AUCUN courriel ne partira : ni les pièces au
> comptable, ni les changements de statut, ni les relances.

Un second avertissement couvre le cas `SMTP_HOST` ou `SMTP_USER` manquant
(`main.py:57-60`).

**L'arbitrage** : couper toute l'application parce que le courriel est muet
serait pire que le mal. Le stock, les notes de frais, les factures et les
remboursements continuent de fonctionner sans SMTP ; l'inventaire ne doit pas
devenir inaccessible parce qu'un serveur de messagerie est en panne. Le drapeau
est par ailleurs indispensable en développement, où « le `.env` local porte les
identifiants du serveur de messagerie réel de l'association, et une séance de
tests sur les notes de frais suffit à écrire à de vrais destinataires »
(`config.py:48-52`).

La contrepartie est que le silence doit être **visible**, et il l'est à trois
endroits : l'avertissement au démarrage (« la première ligne que lit celui qui
diagnostique »), l'endpoint `GET /admin/outbound-emails/etat`, et le fait qu'un
envoi désactivé **échoue** au lieu de retourner en silence — la production a
tourné jusqu'au 2026-08-13 avec « écran tout en vert, boîtes vides » (CLAUDE.md
§6). Ne rien envoyer reste légitime ; le dire « envoyé » ne l'est jamais.

---

## 6. Le webhook HelloAsso

`POST /api/v1/buvette/webhook/helloasso` (`buvette.py:282-327`) est le seul
endpoint **public** de l'API : c'est HelloAsso qui appelle, il n'y a pas de JWT à
présenter.

### Jeton secret dans l'URL

`HELLOASSO_WEBHOOK_SECRET` (`config.py:102-108`) :

> HelloAsso ne signe pas ses notifications ; à défaut de HMAC, un secret dans
> l'URL évite que n'importe qui puisse forger des ventes et décrémenter le
> stock.

Le secret est ajouté en paramètre `token` de l'URL enregistrée chez HelloAsso
(`_default_webhook_url`, `buvette.py:335-342`) : « c'est la seule forme
d'authentification qu'accepte leur système de notifications ».

`_webhook_secret_ok` (`buvette.py:266-279`) compare en **temps constant**
(`secrets.compare_digest`). Si aucun secret n'est configuré, l'appel passe —
comportement historique préservé — mais un avertissement est journalisé :
« l'endpoint est alors ouvert et permet à un tiers de forger des ventes ».

### Validation stricte du schéma

Le corps est d'abord relu en JSON (`buvette.py:298-303`), puis validé par
`HelloAssoWebhookPayload.model_validate` (`buvette.py:305-309`). Tout ce qui
n'est pas conforme est journalisé avec le corps reçu et ignoré. Seuls les types
`Order` et `Payment` déclenchent un traitement ; `Form` est explicitement ignoré
(`buvette.py:313-322`).

### Idempotence par contrainte d'unicité

La clé est `(helloasso_payment_id, helloasso_item_id)`, portée par une
`UniqueConstraint` en base (`models.py:911-921`, `uq_sale_payment_item`).
`record_sale_and_decrement` (`crud/buvette.py:381-455`) cherche d'abord une vente
existante (`_find_existing_sale`, `crud/buvette.py:366`) et sort sans décrémenter
si elle existe. Si deux appels concurrents passent ce test, l'`IntegrityError` de
la contrainte rattrape la course (`crud/buvette.py:446-453`). HelloAsso rejoue
ses notifications : sans cela, un même article décrémenterait le stock plusieurs
fois.

### Réponse 200 systématique

Le endpoint renvoie **toujours 200**, quel qu'ait été le sort de la requête :
secret invalide (`buvette.py:290-297`), JSON illisible (`buvette.py:300-303`),
schéma invalide (`buvette.py:307-309`), exception de traitement
(`buvette.py:323-325`). Deux raisons, toutes deux dans le code :

1. « HelloAsso retries on 5xx; we don't want loops on bad bodies » — un 5xx
   déclenche une tempête de rejeux.
2. Pour le secret invalide en particulier : « un 4xx renseignerait un attaquant
   sur l'existence du secret ».

Les erreurs sont journalisées (`logger.warning` / `logger.exception`), y compris
l'IP de l'appelant lors d'un rejet pour secret invalide.

### Administration du webhook

`POST /buvette/webhook/configure` et `DELETE /buvette/webhook` sont réservés au
Super Admin (`buvette.py:345-354`, `buvette.py:391-399`) ; `GET
/buvette/webhook/status` est ouvert aux administrateurs bénévoles
(`buvette.py:357-388`).

---

## 7. CORS et en-têtes

### CORS

`CORSMiddleware` (`main.py:83-89`) avec `allow_origins=settings.cors_origins`,
`allow_credentials=True`, méthodes et en-têtes libres. La liste vient de
`CORS_ORIGINS` (`config.py:69-72`), séparée par des virgules
(`config.py:161-163`).

Aucun caractère générique n'est utilisé — la liste est explicite. En production,
`_refuse_insecure_production_config` **empêche le démarrage** si une origine
commence par `http://` (`config.py:145-146`).

Attendu en production : `https://stock.lekouttab.fr` uniquement.

### En-têtes de sécurité

Posés **deux fois**, et c'est voulu.

**Par l'application** (`main.py:144-164`), avec `setdefault` pour ne pas écraser
ce qu'un proxy aurait déjà mis :

| En-tête | Valeur |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(self)` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production seulement) |

La CSP est volontairement maximale : « l'API ne rend que du JSON : aucune
ressource n'a besoin d'être chargée ». Exception pour `/docs`, `/redoc` et
`/docs/oauth2-redirect`, qui chargent leurs assets depuis un CDN et « seraient
des pages blanches sous cette politique » — dev uniquement, puisque la
documentation est coupée en production.

La raison de la double pose est donnée en `main.py:141-143` : en développement
(uvicorn seul), Apache n'est pas dans la boucle, et en production « une réponse
servie directement par Passenger ne passe pas toujours par les règles Apache ».

**Par le proxy** (`Caddyfile`, et `.htaccess` pour l'ancienne cible O2Switch),
pour les pages du front :

```
Strict-Transport-Security "max-age=31536000; includeSubDomains"
X-Content-Type-Options "nosniff"
X-Frame-Options "DENY"
Referrer-Policy "strict-origin-when-cross-origin"
Permissions-Policy "geolocation=(), microphone=(), camera=()"
Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
-Server
```

L'en-tête du `Caddyfile` précise que ces valeurs sont « reprises à l'identique
de `.htaccess` : toute divergence changerait le comportement de sécurité sans
qu'on s'en aperçoive ».

`connect-src 'self'` n'est tenable que parce que front et API partagent
l'origine : le front est construit avec `VITE_API_URL=/api/v1`, un chemin
relatif, pas une URL absolue. `-Server` retire la bannière du serveur. HTTPS est
forcé par redirection 301 côté `.htaccess`, et Caddy termine TLS avec
Let's Encrypt.

### Attendu en production, récapitulatif

- `APP_ENV=production`, `APP_DEBUG=false`
- `JWT_SECRET_KEY` et `RIB_ENCRYPTION_KEY` générées et sauvegardées hors dépôt
- `CORS_ORIGINS` en `https://` uniquement
- `HELLOASSO_WEBHOOK_SECRET` renseigné
- `RATE_LIMIT_ENABLED=true`
- `/docs`, `/redoc`, `/openapi.json` fermés (automatique)
- HSTS actif (automatique)

---

## 8. Points de vigilance

Ce qui mérite attention **sans être un défaut avéré** : ce sont des arbitrages
documentés, des limites connues du contexte d'hébergement, ou des écarts entre
deux protections voisines.

**Limitation de débit non partagée entre workers.** Le compteur `slowapi` vit en
mémoire de process (`rate_limit.py:8-12`) : avec N workers, la limite effective
est N fois celle annoncée. Le verrouillage après échecs (§1.5), lui, est persisté
en base et ne souffre pas de ce défaut — c'est la protection réellement
contraignante sur `/auth/login`. À réévaluer si un Redis devient disponible.

**Clé du limiteur = adresse IP seule.** `get_remote_address` est utilisé sans
clé composite. Derrière un proxy, tout dépend de la fidélité de l'adresse
transmise ; plusieurs utilisateurs derrière la même sortie NAT partagent le
compteur.

**Jetons en `localStorage`.** Le store Zustand est persisté
(`frontend/src/stores/auth.ts:17-37`). C'est l'arbitrage annoncé dans CLAUDE.md
§7 (« httpOnly cookie ou localStorage selon trade-off — par défaut localStorage +
rotation »). La rotation avec détection de rejeu (§1.2) limite la fenêtre
d'exploitation d'un vol, et la CSP stricte réduit le risque d'injection ; le
stockage reste néanmoins lisible par tout script s'exécutant sur l'origine.

**Le document RIB n'est pas chiffré, l'IBAN l'est.** Deux formes de la même
donnée bancaire, deux niveaux de protection (§3.2). L'écart est motivé — un BLOB
traverse mal `ChampChiffre`, conçu pour du texte — mais il signifie qu'un export
de base expose les documents alors qu'il n'expose pas les IBAN.

**Pas d'AAD sur le chiffrement du RIB.** Documenté en `crypto.py:20-25` : le
chiffré n'est pas lié à sa ligne, donc déplaçable d'un compte à l'autre par
quelqu'un ayant déjà les droits d'écriture MySQL. Modèle de menace assumé.

**Webhook ouvert si `HELLOASSO_WEBHOOK_SECRET` est vide.**
`_webhook_secret_ok` (`buvette.py:274-278`) laisse alors passer, en journalisant
un avertissement. Ce comportement historique est conservé pour ne pas casser une
installation existante, mais il n'est bloqué par aucun contrôle de démarrage,
contrairement à `RIB_ENCRYPTION_KEY`. Un secret vide en production reste
détectable seulement dans les journaux.

**Le secret du webhook voyage dans l'URL.** Contraint par HelloAsso, qui n'offre
pas de HMAC (`config.py:102-105`). Une URL apparaît dans les journaux d'accès du
proxy. La comparaison en temps constant est en place ; la rotation du secret
suppose de reconfigurer le webhook chez HelloAsso.

**Le webhook répond toujours 200.** Nécessaire pour éviter les tempêtes de
rejeu, mais cela signifie qu'un envoi rejeté (mauvais secret, schéma invalide)
n'est visible que dans les journaux. Sans surveillance de ces journaux, une
tentative d'abus passe inaperçue.

**Réponse identique en cas de secret invalide et de traitement réussi.**
Voulu — ne pas renseigner un attaquant — mais rend le diagnostic d'une
configuration erronée dépendant des journaux serveur.

**Vérification de rôle dupliquée entre front et back.** La matrice
`frontend/src/lib/auth.ts` doit refléter les dépendances serveur ; plusieurs
commentaires le rappellent nommément (`auth.ts:59`, `auth.ts:64-65`,
`auth.ts:69-70`, `auth.ts:72-73`). Aucune vérification automatique ne garantit
l'alignement : une divergence produit un bouton visible qui échoue en 403, ce qui
est le bon sens de l'erreur, mais reste une friction.

**Contrôles de propriété écrits à la main, endpoint par endpoint.** Le test
`row.id_user != current_user.id` est répété dans `expenses.py`, `invoices.py`,
`reimbursements.py` et `users.py` plutôt que factorisé en dépendance. C'est
lisible localement, mais chaque nouvel endpoint servant un objet possédé doit y
penser explicitement — et les identifiants entiers séquentiels rendent l'oubli
immédiatement exploitable.

**Hachages hérités SHA-256 encore acceptés.** `verify_password_legacy`
(`security.py:43-53`) permet la connexion sur un hachage SHA-256 nu issu de la
version Streamlit, avec bascule forcée ensuite (`password_must_change`). Le
chemin doit disparaître le jour où plus aucun compte n'est dans ce cas.

**`_bcrypt_safe` tronque silencieusement à 72 octets** (`security.py:19-22`).
Conforme à bcrypt, mais deux mots de passe partageant leurs 72 premiers octets
sont équivalents, sans que l'utilisateur en soit informé.

**Le repli disque des justificatifs subsiste.** `contenu_du_fichier`
(`files.py:352-367`) lit la base en priorité et le disque à défaut, pour les
pièces antérieures à la migration. Le chemin disque est confiné par
`_is_inside_uploads`, mais ce code « disparaîtra le jour où plus aucune ligne ne
sera dans ce cas » — tant qu'il vit, il maintient une seconde source de lecture.

**`allow_headers=["*"]` et `allow_methods=["*"]` en CORS** (`main.py:83-89`).
Sans conséquence tant que la liste d'origines reste stricte et vérifiée au
démarrage, mais cela repose entièrement sur cette liste.

**Conversion PDF non rétroactive.** Les justificatifs déposés avant l'activation
de `convertir_en_pdf` restent des images en base. Aucun risque de sécurité, mais
deux formats coexistent pour la même famille de documents.
