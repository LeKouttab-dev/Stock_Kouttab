# 01 — Architecture du backend

> Périmètre : le backend FastAPI (`backend/app/`). Ce document décrit les couches,
> les parcours métier de bout en bout et les mécanismes transverses.
>
> Ne sont **pas** traités ici : le modèle de données détaillé
> (`docs/02-MODELE-DE-DONNEES.md`), le frontend (`docs/04-FRONTEND.md`), la
> sécurité (`docs/05-SECURITE.md`), les environnements et le déploiement
> (`docs/06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md`), les tests (`docs/07-TESTS.md`).
>
> Toutes les références de code sont données sous la forme `chemin:ligne`,
> relatives à `Gestion_stock_kouttab_react/`.

---

## 1. Vue d'ensemble

### À quoi sert l'application

**Kouttâb Stock** est l'outil de gestion interne de l'institut associatif
**Le Kouttâb**. Il est la réécriture React + FastAPI d'une application Streamlit
antérieure, et **conserve la base MySQL existante** — le schéma est partagé avec
le legacy (`CLAUDE.md:9`, `CLAUDE.md:43`).

Cinq domaines y cohabitent :

1. **Inventaire** — articles, catégories, sous-catégories, seuils d'alerte, et un
   circuit de demande de modification pour les bénévoles
   (`backend/app/api/v1/endpoints/stock.py`, `backend/app/crud/stock.py`).
2. **Notes de frais** — un bénévole avance de l'argent, dépose ses tickets, la
   comptabilité valide puis rembourse (`backend/app/api/v1/endpoints/expenses.py`,
   `backend/app/crud/expense.py`, `backend/app/crud/reimbursement.py`).
3. **Factures** — pièces fournisseur déposées par les bénévoles, traitées par la
   comptabilité (`backend/app/api/v1/endpoints/invoices.py`,
   `backend/app/crud/invoice.py`).
4. **Buvette HelloAsso** — les produits sont synchronisés depuis la boutique
   HelloAsso, et le stock est décrémenté automatiquement à chaque vente reçue par
   webhook (`backend/app/crud/buvette.py`, `backend/app/services/helloasso.py`).
5. **Vie du compte et échanges** — invitations, validation des inscriptions, fils
   de discussion avec l'équipe, tickets de justificatif manquant
   (`backend/app/api/v1/endpoints/invitations.py`, `.../contact.py`,
   `.../tickets.py`).

Le fil rouge de l'application n'est pas le stock : c'est **la pièce comptable**.
Une facture ou une note de frais déposée dans l'application doit arriver chez le
comptable sous un nom exploitable, en PDF, sans perte ni doublon. Une bonne
partie des mécanismes décrits en §4 n'existe que pour cela.

### Qui s'en sert

- Les **bénévoles** de l'association, qui consultent le stock, déposent leurs
  notes de frais et leurs factures depuis un téléphone (le dépôt le plus courant
  est une photo prise sur iOS, d'où le soin porté au format HEIC —
  `backend/app/services/files.py:29-32`).
- Les **administrateurs bénévoles**, qui tiennent l'inventaire et la buvette.
- La **comptabilité**, qui valide, refuse, rembourse et archive.
- Le **Super Admin**, qui administre les comptes, les référentiels et le
  déploiement des invitations.

### Les quatre rôles

Ils sont portés par la colonne `Admins.role`, en chaîne libre validée
applicativement (`CLAUDE.md:189`), et vérifiés par la dépendance
`require_roles` (`backend/app/api/deps.py:44-56`) :

| Rôle | Ce qu'il fait |
|---|---|
| **Benevole** | Consulte le stock, demande une modification, dépose notes de frais et factures, suit ses remboursements. |
| **AdminBenevoles** | Le précédent, plus la gestion directe de l'inventaire (CRUD articles/catégories, approbation des demandes, import CSV) et la buvette (synchronisation, ajustement de stock). |
| **Compta** | Valide, refuse, commente notes de frais et factures ; enregistre les remboursements ; écarte un justificatif ; ouvre et relance les tickets de justificatif ; lit le RIB des bénévoles. |
| **Super Admin** | Tout ce qui précède, plus la gestion des comptes et des rôles, les invitations, l'export/import de base, la configuration du webhook HelloAsso, et la suppression définitive d'une note. |

La matrice complète action par action est en `CLAUDE.md:215-250`. Les détails
d'application (dépendances FastAPI, contrôles de propriété) relèvent de
`docs/05-SECURITE.md`.

En pratique, les endpoints regroupent souvent les deux rôles comptables sous une
constante locale, par exemple `_ACCOUNTANT_ROLES = ("Compta", "Super Admin")`
(`backend/app/api/v1/endpoints/expenses.py:43`,
`backend/app/api/v1/endpoints/invoices.py:57`,
`backend/app/api/v1/endpoints/reimbursements.py:27`).

---

## 2. Les couches et leurs droits

Le backend est découpé en cinq couches. Ce découpage n'est pas décoratif : il est
vérifiable, et il l'est aujourd'hui (voir « ce qui est réellement vrai » ci-après).

```
HTTP  ──►  api/v1/endpoints/   validation d'entrée, permissions, sérialisation
             │                 ▲
             ▼                 │
           crud/               règles métier, transactions, invariants
             │                 ▲
             ▼                 │
           services/           effets de bord : courriel, fichiers, PDF, HelloAsso
             │                 ▲
             ▼                 │
           db/                 modèles SQLAlchemy, session, types de colonnes
                               core/  transversal : config, sécurité, erreurs,
                                      workflow, money
```

### `api/v1/endpoints/` — la frontière HTTP

**A le droit de** : déclarer les routes, lire les paramètres (`Form`, `File`,
`Query`, corps Pydantic), convertir et valider les entrées primitives, appliquer
les permissions, orchestrer l'appel au CRUD puis aux services, choisir la forme
de la réponse, et programmer des `BackgroundTasks`.

**Exemples** : `_parse_decimal` et `_parse_date`
(`backend/app/api/v1/endpoints/expenses.py:83-116`) traduisent une chaîne de
formulaire en `Decimal`/`date` et lèvent une `AppException` typée ; `_to_out`
(`.../expenses.py:69-74`) masque le RIB quand le demandeur n'a pas le droit de le
voir, en s'appuyant sur `_can_see_rib` (`.../expenses.py:77-80`).

**Ne doit pas** : contenir de règle métier durable. Le cas
`invoices._serialize_invoice` est instructif : la fonction délègue désormais au
CRUD, avec le commentaire « ce module en avait une copie, qui divergeait dès que
le modèle gagnait un champ » (`backend/app/api/v1/endpoints/invoices.py:368-371`,
la fonction de référence étant `backend/app/crud/invoice.py:18-59`).

**Ne doit pas non plus** être la seule à porter un contrôle d'accès sensible :
les endpoints déclarent `dependencies=[Depends(require_roles(...))]`, mais le
CRUD revérifie le rôle pour les gestes destructeurs — `archive_expense`
(`backend/app/crud/expense.py:337-340`), `supprimer_definitivement`
(`.../expense.py:365-369`), `ecarter_fichier` (`.../expense.py:439-442`). La
double barrière est délibérée : un endpoint futur qui appellerait le CRUD sans la
dépendance ne pourrait pas contourner la règle.

### `crud/` — les règles métier, sans FastAPI

**A le droit de** : lire et écrire via SQLAlchemy, valider les invariants métier,
gérer les transactions (`db.commit()`, `db.flush()`), lever des `AppException`,
et appeler des services (`crud/reimbursement.py` appelle `naming`, `outbox` et
`reimbursement_doc` — `backend/app/crud/reimbursement.py:36`).

**Ne doit pas importer FastAPI.** C'est vérifié : aucune occurrence de `fastapi`
dans `backend/app/crud/`. Les modules manipulent donc des types du domaine
(`Decimal`, `date`, modèles ORM), jamais un `UploadFile` ni une `Response`.

**Ne doit pas** dépendre du transport : `crud.expense.marquer_lues`
(`backend/app/crud/expense.py:89-101`) est explicitement séparée de la lecture,
« `list_expenses_for_user` sert aussi à construire des courriels et des exports,
où éteindre un signal n'aurait aucun sens. Seul l'endpoint qui répond à un écran
appelle cette fonction ».

C'est aussi le CRUD qui porte les décisions les plus fines. `validate_expense`
(`backend/app/crud/expense.py:255-320`) refuse de sortir une note de
« Remboursée » dès qu'un versement lui est rattaché (`:275-287`), refuse qu'on
déclare « Remboursée » à la main avec un message explicite plutôt que l'erreur
générique du graphe (`:292-300`), puis délègue le contrôle de transition à
`core.workflow` (`:302`).

### `services/` — les effets de bord

**A le droit de** : parler au monde extérieur — SMTP (`email.py`), système de
fichiers (`files.py`), conversion PDF (`pdf.py`), HTTP sortant vers HelloAsso
(`helloasso.py`), production de documents (`reimbursement_doc.py`), et la file
d'envoi persistante (`outbox.py`).

**Trois services touchent la base**, et c'est assumé :
`services/outbox.py`, `services/compta_dispatch.py` et `services/csv_import.py`.
`outbox` est un *transactional outbox* : son objet même est d'écrire une ligne
`OutboundEmails` (`backend/app/services/outbox.py:1-14`). `compta_dispatch`
assemble naming + PDF + file et met en file (`.../compta_dispatch.py:1-8`). Les
autres services sont purs vis-à-vis de la base.

**Deux services touchent FastAPI**, de façon bornée : `files.py` importe
`UploadFile` (`backend/app/services/files.py:11`) parce qu'il consomme le flux
d'upload par morceaux, et `email.py` importe `fastapi_mail`
(`backend/app/services/email.py:9`). Aucun service n'importe `APIRouter`,
`Depends` ni `Request`.

**Deux services sont volontairement purs**, et le disent :
- `services/naming.py` — « Module volontairement pur : aucune I/O, aucun accès
  base, aucune dépendance à FastAPI. Il est donc testable exhaustivement […] et
  dupliqué à l'identique côté frontend » (`backend/app/services/naming.py:16-19`).
- `services/reimbursement_doc.py` — « Module volontairement pur : il ne connaît
  ni la base ni FastAPI, ce qui le rend testable sur des objets quelconques »
  (`backend/app/services/reimbursement_doc.py:14-16`).

**Ne doit pas** décider du métier. `compta_dispatch` ne choisit pas *si* une
pièce doit partir : il compose et met en file ce qu'on lui donne. La décision
d'exclure une pièce écartée est portée par le filtre à l'appel
(`backend/app/services/compta_dispatch.py:178`), avec la raison en commentaire :
« Une pièce écartée ne part pas au comptable : c'est justement lui qui l'a
retirée du dossier. »

### `db/` — modèles, session, types de colonnes

- `db/models.py` : les modèles SQLAlchemy. Le schéma est **partagé avec le
  legacy Streamlit** et ne bouge que par migration Alembic explicite
  (`CLAUDE.md:890`, `CLAUDE.md:944-945`).
- `db/session.py` : l'`Engine` et la `sessionmaker`. Deux réglages y sont
  justifiés par le fait que la base est distante : `pool_pre_ping=True` — « teste
  la connexion avant de la prêter : indispensable avec une base distante, qui
  peut couper une connexion inactive sans que le client en soit informé »
  (`backend/app/db/session.py:23-26`) — et `pool_recycle`, réglable par
  l'environnement (`backend/app/core/config.py:33-39` : « `recycle` doit rester
  SOUS le `wait_timeout` du serveur (souvent 300 s), sinon on réutilise des
  connexions déjà fermées d'en face »).
- `db/session.py:42-48` : `get_db`, la dépendance FastAPI qui ouvre et ferme une
  session par requête. Les tâches de fond, elles, **ouvrent leur propre session**
  — la session de la requête est déjà fermée quand elles s'exécutent
  (`backend/app/services/outbox.py:239-254`,
  `backend/app/api/v1/endpoints/expenses.py:579-592`).
- `db/types.py` : `ChampChiffre`, colonne texte chiffrée AES-256-GCM. Le
  chiffrement est placé « à la frontière de la base plutôt que dans le CRUD :
  tout ce qui lit ou écrit `Admin.rib` passe par lui, y compris le code écrit
  plus tard qui ignorerait tout du sujet. Un chiffrement qu'on peut oublier
  d'appeler finit toujours par être oublié quelque part »
  (`backend/app/db/types.py:1-8`, `:24-31`). Détails en `docs/05-SECURITE.md`.

**Ne doit pas** contenir de logique métier ni d'accès réseau.

### `core/` — le socle transversal

| Module | Rôle | Point notable |
|---|---|---|
| `core/config.py` | `Settings` Pydantic lus depuis `.env`, en singleton `lru_cache` (`:191-197`) | Refuse le démarrage en production si `JWT_SECRET_KEY` est resté au défaut, si `APP_DEBUG` est vrai, si une origine CORS est en `http://`, ou si `RIB_ENCRYPTION_KEY` est vide (`:127-159`). « Mieux vaut un refus de démarrage bruyant qu'une application ouverte silencieusement. » |
| `core/security.py` | bcrypt, JWT, validations | `_bcrypt_safe` borne le mot de passe à 72 octets, limite dure de bcrypt (`:19-22`) |
| `core/errors.py` | Catalogue unique des codes d'erreur (`AUTH_1001`, `RATE_7001`…) | La procédure d'ajout impose de **refléter le code dans `frontend/src/lib/errors.ts`** (`:18-22`) |
| `core/exceptions.py` | `AppException` + enregistrement des handlers FastAPI | Seule exception à la règle « `core` ignore FastAPI » : le module importe `FastAPI`/`Request`/`JSONResponse` (`:18-20`) parce qu'il **est** la couche de traduction erreur → réponse HTTP |
| `core/workflow.py` | Graphe des transitions de statut | Cf. §4.4 |
| `core/money.py` | Montant dû au bénévole | Jumeau de `frontend/src/lib/money.ts`, cf. §5 |
| `core/reimbursement_options.py` | Moyens et établissements de paiement, listes figées | Servies au front par `GET /reimbursements/options` plutôt que recopiées (`backend/app/api/v1/endpoints/reimbursements.py:43-60`) |
| `core/rate_limit.py`, `core/logger.py`, `core/crypto.py` | Limiteur slowapi partagé, logger, primitives de chiffrement | — |

### Ce qui ne doit pas traverser

| Interdit | Pourquoi |
|---|---|
| `fastapi` dans `crud/` | Le CRUD doit être appelable depuis un script (`backend/scripts/process_outbound_emails.py:31` appelle `crud.ticket`), un test ou un futur worker. Vérifié : zéro occurrence. |
| `UploadFile`, `Request`, `Response` sous `crud/` | Le CRUD reçoit des `bytes`, un `Decimal`, une `date` — jamais un objet de transport. `attach_file` prend `contenu: bytes` (`backend/app/crud/expense.py:186-207`). |
| Règle métier dans `endpoints/` | Elle finit dupliquée entre l'écran facture et l'écran note de frais. Le contre-exemple corrigé : `crud/rattachement.py`, cf. §4.3. |
| Sérialisation dupliquée entre `endpoints/` et `crud/` | Voir `serialize_invoice` (`backend/app/crud/invoice.py:18-23`) : « Point unique de vérité : l'endpoint avait sa propre copie de cette fonction, ce qui garantissait qu'un champ ajouté ici manquerait là. » |
| Accès direct au SMTP depuis un endpoint | Tout envoi critique passe par `outbox.enqueue`, jamais par `email._send_raw` directement. |
| Chiffrer/déchiffrer un RIB à la main | `ChampChiffre` s'en charge (`backend/app/db/types.py`). |

### Le montage de l'application

`backend/app/main.py` assemble le tout :

- `lifespan` (`:30-64`) crée `UPLOAD_DIR` et `OUTBOX_DIR`, sème les référentiels
  par défaut (pôles, catégories de dépense) parce que « les tests et les
  environnements de développement montent le schéma via `create_all()` sans jouer
  les migrations » (`:35-37`), et **journalise un avertissement si
  `EMAIL_ENABLED=false`** (`:48-56`) — « Un courriel coupé ne se voit nulle part
  tant que personne ne dépose de pièce : la production a tourné trois semaines
  ainsi. »
- La documentation interactive (`/docs`, `/redoc`, `/openapi.json`) est
  **désactivée en production** (`:67-79`).
- Trois middlewares maison : plafond de taille de requête `MAX_REQUEST_MB`
  (`:121-138`, ajouté parce que « la limite n'existait pas »), en-têtes de
  sécurité (`:144-164`), et journal de durée par requête (`:168-181`).
- `register_exception_handlers(app)` (`:185`) puis
  `app.include_router(api_router, prefix="/api/v1")` (`:189`).
- Le routeur v1 agrège seize sous-routeurs
  (`backend/app/api/v1/router.py:27-43`).

---

## 3. Les parcours importants, tracés bout en bout

### 3.1 Dépôt d'une note de frais

`POST /api/v1/expenses` — `backend/app/api/v1/endpoints/expenses.py:151-259`.
Multipart : champs de formulaire + jusqu'à 5 fichiers.

| # | Étape | Où |
|---|---|---|
| 1 | Authentification, compte actif | `deps.get_current_user` (`backend/app/api/deps.py:22-41`) |
| 2 | Le fournisseur est obligatoire | `.../expenses.py:180-183` |
| 3 | **Résolution du rattachement, avant toute écriture** | `rattachement_crud.resoudre` (`backend/app/crud/rattachement.py:49-118`) |
| 4 | Création de la ligne, statut `En attente` | `expense_crud.create_expense` (`backend/app/crud/expense.py:140-183`) |
| 5 | Plafond de 5 fichiers | `.../expenses.py:219-220` (`ErrorCode.TOO_MANY_FILES`) |
| 6 | Pour chaque fichier : validation MIME, écriture disque, **conversion PDF**, lecture du contenu | `files.save_upload_file(upload, "expenses", convertir_en_pdf=True)` (`backend/app/services/files.py:164-256`) |
| 7 | Rattachement du fichier à la note, **contenu stocké en base** | `expense_crud.attach_file` (`backend/app/crud/expense.py:186-207`) |
| 8 | Notification « nouvelle note » à la comptabilité, en tâche de fond | `.../expenses.py:234-244` → `_notify_new_expense_safe` (`:570-592`) → `email_service.send_new_expense_notification` (`backend/app/services/email.py:244-274`) |
| 9 | **Préparation et mise en file du circuit comptable, synchrone** | `compta_dispatch.prepare_expense_dispatch` (`backend/app/services/compta_dispatch.py:167-229`) |
| 10 | Tentative d'envoi immédiate, en tâche de fond | `background.add_task(outbox.try_send_now, row.id)` (`.../expenses.py:254`) |
| 11 | Réponse sérialisée, RIB masqué si besoin | `_to_out` (`.../expenses.py:69-74`) |

**Le point structurant est l'étape 9.** Le commentaire du code l'explique :
« Envoi des tickets au comptable, même chaîne que les factures. **Synchrone
jusqu'à la mise en file** : une conversion PDF ratée doit remonter au déposant,
pas disparaître dans une tâche de fond » (`.../expenses.py:246-248`). Seul
l'envoi SMTP est asynchrone.

Détail de l'étape 9, dans `_prepare_attachments`
(`backend/app/services/compta_dispatch.py:44-82`) :

1. Les pièces **écartées** sont exclues en amont
   (`.../compta_dispatch.py:178`).
2. Un nom est calculé par pièce via `naming.build_attachment_filename`
   (`:55`), puis dédupliqué par `naming.deduplicate_filenames` (`:57`).
3. `files_service.materialiser` rend le fichier accessible sur disque — depuis le
   disque s'il y est, réécrit depuis la base sinon (`:66`, et
   `backend/app/services/files.py:370-393`).
4. `pdf.ensure_pdf` produit le PDF sous son nom définitif (`:73-75`,
   `backend/app/services/pdf.py:186-213`).
5. `_split_by_size` découpe en plusieurs courriels si le total dépasse
   `MAX_ATTACHMENT_TOTAL_MB` (`:85-104`) : « Dix fichiers de 10 Mo dépassent très
   largement ce qu'accepte un SMTP mutualisé. Plutôt que d'échouer, on découpe. »
6. `outbox.enqueue` écrit une ligne `OutboundEmails` par lot (`:216-228`).

La date qui datera le fichier est `expense.date_evenement or expense.date_depense`
(`:174`) : « La date de l'événement fait foi ; à défaut […] on retombe sur la date
de la dépense pour ne jamais produire un "NC". »

### 3.2 Dépôt d'une facture

`POST /api/v1/invoices` — `backend/app/api/v1/endpoints/invoices.py:130-216`.
Le parcours est délibérément **le même**, aux paramètres près.

| # | Étape | Où | Différence avec la note de frais |
|---|---|---|---|
| 1 | Au moins un fichier, 10 maximum | `.../invoices.py:149-156` | Le fichier est **obligatoire** (`files: list[UploadFile] = File(...)`, `:145`) ; il est facultatif sur une note |
| 2 | Résolution du rattachement | `rattachement_crud.resoudre` (`.../invoices.py:161-168`) | Identique — c'est tout l'objet du module partagé |
| 3 | Création, statut `En attente` | `invoice_crud.create_invoice` (`backend/app/crud/invoice.py:219-253`) | — |
| 4 | Fichiers : validation, disque, PDF, base | `save_upload_file(upload, "invoices", convertir_en_pdf=True)` (`.../invoices.py:189-198`) | Sous-dossier `invoices` |
| 5 | Circuit comptable, synchrone | `compta_dispatch.prepare_invoice_dispatch` (`backend/app/services/compta_dispatch.py:110-161`) | La date de repli est `date_depot` et non `date_depense` (`:119-120` : « Sans événement, sa date n'existe pas : le dépôt fait foi. ») |
| 6 | Notification compta + envois en tâche de fond | `.../invoices.py:210-214` | — |

Le commentaire de l'étape 5 reprend mot pour mot la même justification :
« Conversion PDF et mise en file : synchrone et dans la transaction. Si la
conversion échoue, le déposant le voit immédiatement au lieu de croire sa pièce
partie. Seul l'envoi SMTP part en tâche de fond » (`.../invoices.py:204-206`).

Une relance manuelle existe des deux côtés, réservée à la comptabilité :
`POST /invoices/{id}/resend-compta-email` (`.../invoices.py:219-239`) et
`POST /expenses/{id}/resend-compta-email` (`.../expenses.py:262-280`). Elle crée
**une nouvelle ligne** de file, l'historique précédent étant conservé
(`.../invoices.py:230`).

### 3.3 Validation d'une note et notification du déposant

`PATCH /api/v1/expenses/{id}/validate` —
`backend/app/api/v1/endpoints/expenses.py:305-380`, réservé à
`_ACCOUNTANT_ROLES` (`:308`).

1. **Le statut d'avant est capturé** (`:319-320`) : « sans lui, impossible de
   savoir si l'on annonce un changement ou un simple commentaire ».
2. `expense_crud.validate_expense` (`backend/app/crud/expense.py:255-320`)
   applique dans l'ordre :
   - refus de sortir de « Remboursée » si un versement est rattaché (`:275-287`) ;
   - refus de déclarer « Remboursée » à la main, avec un message qui renvoie vers
     le bouton « Rembourser » (`:292-300`) ;
   - `check_expense_transition` (`:302`), le graphe de `core/workflow.py` ;
   - calcul de `a_bouge` — statut **ou** commentaire (`:307-309`) ;
   - horodatage `validated_by` / `validated_at` uniquement si le statut change
     (`:311-313`) ;
   - `non_lu_demandeur = True` si quelque chose a bougé (`:316-317`).
3. Retour dans l'endpoint : `doit_notifier_du_statut`
   (`backend/app/services/email.py:348-357`) écarte le cas où le valideur est
   aussi le destinataire — « Il vient de faire l'action : lui écrire pour la lui
   annoncer n'apprend rien et noie les notifications utiles. »
4. **Le message dit la vérité** (`.../expenses.py:339-351`) : si le statut a
   changé, objet et introduction viennent de `_INTRO_STATUT` / `_SUITE_STATUT`
   (`.../expenses.py:49-66`) ; sinon l'objet devient « message de la
   comptabilité » et le corps précise « Son statut n'a pas changé ». Le
   commentaire du code : « Le courriel annonçait "votre note a été approuvée" même
   quand SEUL le commentaire changeait […]. Un message qui se trompe sur ce qu'il
   annonce finit par être ignoré, y compris les fois où il dit vrai. »
5. **L'envoi passe par la file**, `outbox.enqueue(kind="statut_note", …)`
   (`.../expenses.py:356-377`), puis `try_send_now` en tâche de fond (`:378`).
   Raison : « c'est le seul avis que reçoit le déposant, et un échec SMTP le
   faisait disparaître sans laisser de trace nulle part » (`:353-355`).
6. Le corps est composé par `email_layout.composer`
   (`backend/app/services/email_layout.py`), avec le prénom du déposant
   (`crud/expense.py:52-54` : « Sert la salutation des courriels »).

**Extinction de la pastille.** `non_lu_demandeur` s'éteint quand le déposant
ouvre sa liste : `GET /expenses/me` appelle `expense_crud.marquer_lues`
**après** la sérialisation (`.../expenses.py:126-131`) — « sinon l'écran qui vient
de l'allumer ne la montrerait jamais ».

Le parcours facture est le jumeau : `PATCH /invoices/{id}/status`
(`backend/app/api/v1/endpoints/invoices.py:245-312`) → `invoice_crud.update_status`
(`backend/app/crud/invoice.py:280-310`) → même `outbox.enqueue`, `kind="statut_facture"`.

### 3.4 Remboursement groupé et production du justificatif

`POST /api/v1/reimbursements` —
`backend/app/api/v1/endpoints/reimbursements.py:90-111`, réservé à la
comptabilité. Toute la logique est dans
`crud.reimbursement.create_reimbursement` (`backend/app/crud/reimbursement.py:230-274`).

Le principe est posé en tête de module : « La comptabilité ne rembourse pas note
par note — elle vire un montant à un bénévole. […] Tout se joue dans **une seule
transaction** : le statut des notes, le remboursement et les documents. Un échec
à mi-chemin laisserait des notes marquées "Remboursé" sans justificatif, ou
l'inverse — deux états qu'aucun écran ne permettrait de rattraper »
(`backend/app/crud/reimbursement.py:1-11`).

| # | Étape | Où |
|---|---|---|
| 1 | **Contrôle tout ou rien** du lot | `_controler_les_notes` (`:129-190`) |
| 2 | Création du versement, `montant_total` figé | `:244-254` |
| 3 | `db.flush()` pour obtenir l'identifiant | `:256` — « attribue l'identifiant, qui nomme le dossier des documents » |
| 4 | Les notes passent à `Remboursée` et pointent le versement | `:258-260` |
| 5 | **Production du PDF et du tableur** | `_ecrire_documents` (`:193-227`) |
| 6 | Chemins **et contenus** enregistrés | `:263-268` |
| 7 | `db.commit()` | `:270` |
| 8 | Mise en file, **après** le commit | `_mettre_en_file` (`:277-362`) |

Détail de l'étape 1 (`:129-190`) : lot non vide, toutes les notes existent,
**un seul bénévole**, aucune note déjà rattachée à un versement, toutes en
statut « Approuvée ». Le refus est global : « rembourser trois notes sur quatre
en silence, parce que la quatrième avait déjà été payée, ne se verrait qu'au
moment du rapprochement bancaire » (`:132-135`).

Détail de l'étape 5 (`:193-227`) : les documents sont écrits dans
`OUTBOX_DIR/reimbursement/{id}/`, **hors de `uploads/`** — « ces fichiers portent
des noms prévisibles, et le serveur web laisse passer `uploads/` » (`:196-200`).
Le nom du fichier est produit par `naming.build_attachment_stem(["NDF", nom],
date)` (`:217-220`) pour rester ASCII pur. Le contenu vient de
`reimbursement_doc.construire_pdf` / `construire_xlsx` (`:224-225`), module pur
qui reprend la disposition du modèle « NDF - Nom Prénom » fourni par le client
(`backend/app/services/reimbursement_doc.py:1-6`). Le tableur est **reconstruit,
pas rempli** : `openpyxl` mutilerait le modèle à la réécriture (`:8-12`).

Détail de l'étape 8 (`:277-362`) : **deux envois distincts**, pas un envoi à deux
destinataires. « Le comptable archive une opération, le bénévole reçoit une
preuve. Les deux ne se disent pas de la même façon » (`:295-298`). L'envoi à la
comptabilité est déposé **sans condition**, même si `COMPTA_EMAIL` est vide
(`:329-342`) ; l'envoi au bénévole n'a lieu que s'il a une adresse (`:347`) —
« un compte sans courriel n'est pas une configuration à corriger plus tard, et la
ligne resterait en attente pour toujours ».

Le montant est calculé par `core.money.total_a_rembourser` (`:251`), et le
plafonnement à zéro s'applique **par note** : « une note soldée d'avance ne doit
pas venir amputer le remboursement d'une autre »
(`backend/app/core/money.py:55-61`).

**Restitution du justificatif** : `GET /reimbursements/{id}/document?format=pdf|xlsx`
(`backend/app/api/v1/endpoints/reimbursements.py:114-139`), accessible au
bénévole concerné — « c'est la preuve de son remboursement » (`:123`). Le contenu
vient de `contenu_document` (`backend/app/crud/reimbursement.py:365-385`) : la
base d'abord, repli disque pour les versements antérieurs à la migration
`d0f7b2c5e8a9`. Et `a_un_document` (`:388-397`) teste la présence **réelle** :
« `bool(chemin_pdf)` renvoyait vrai pour un fichier disparu : l'écran promettait
un téléchargement qui rendait un 404. »

### 3.5 Vente HelloAsso via webhook

`POST /api/v1/buvette/webhook/helloasso` —
`backend/app/api/v1/endpoints/buvette.py:282-327`. **Endpoint public**, sans JWT :
c'est HelloAsso qui appelle.

| # | Étape | Où |
|---|---|---|
| 1 | Vérification du secret d'URL, en temps constant | `_webhook_secret_ok` (`:266-279`) |
| 2 | Lecture du JSON | `:298-303` |
| 3 | Validation du schéma Pydantic | `HelloAssoWebhookPayload.model_validate` (`:305-309`) |
| 4 | Aiguillage par `eventType` : `Order`, `Payment`, `Form` | `:312-322` |
| 5 | Pour chaque item de la commande | `_process_order` (`:183-263`) |
| 6 | Enregistrement idempotent + décrément | `buvette_crud.record_sale_and_decrement` (`backend/app/crud/buvette.py:381-463`) |
| 7 | Alerte de stock bas, en tâche de fond | `:239-252` → `_send_buvette_alert_safe` (`:407-420`) |

**La règle qui gouverne tout l'endpoint : toujours répondre 200.** Un secret
invalide rend `{"status": "ignored"}` avec un 200, et le commentaire dit pourquoi
— « 200 volontaire : un 4xx renseignerait un attaquant sur l'existence du secret,
et HelloAsso ne doit de toute façon jamais voir d'erreur » (`:295-297`). Idem
pour un JSON invalide (`:302`), un schéma non conforme (`:309`) et une exception
de traitement (`:323-325`) : « Always return 200 to avoid HelloAsso retry
storms. » Chaque item est de plus traité dans son propre `try` (`:262-263`) :
un item cassé n'emporte pas les autres.

**L'idempotence** repose sur la clé `(helloasso_payment_id, helloasso_item_id)`
(`backend/app/crud/buvette.py:397`). Si la vente existe déjà, on retourne sans
décrémenter (`:406-413`). La contrainte UNIQUE en base est le filet de dernier
recours : en cas de course entre deux workers, l'`IntegrityError` est rattrapée
et la vente existante renvoyée (`:444-458`).

**Le décrément** est borné : `quantity = max(0, quantity - quantity_sold)`
(`:438`). Le drapeau `alert_sent` retombe dès que le stock repasse au-dessus du
seuil (`:440-441`), et il est **posé avant** la tâche de fond d'envoi
(`backend/app/api/v1/endpoints/buvette.py:245-246` : « Flag now to avoid
duplicate emails before the background task runs »).

**Un produit inconnu ne bloque rien** : `product` peut valoir `None` si le tier
n'a pas encore été synchronisé (`backend/app/crud/buvette.py:415`). La vente est
enregistrée quand même, avec `product_name_snapshot` (`:423`) — la trace de la
recette est conservée même sans article local.

**La synchronisation** (`POST /buvette/sync`,
`backend/app/api/v1/endpoints/buvette.py:115-134`) obéit à une règle de
souveraineté du stock local (`backend/app/crud/buvette.py:254-266`) : nouveau
produit → on copie la quantité HelloAsso ; produit existant à 0 → on copie ;
produit existant à quantité non nulle → **on ne touche jamais**. Deux
extracteurs défensifs valent d'être signalés : `_extract_helloasso_price_cents`
(`:183-207`) rend `None` et non `0` quand le prix est introuvable — « un prix
absent n'est pas un prix nul » — et l'appelant ne l'écrase alors pas (`:334-335`,
« sinon une synchronisation remet à 0 EUR tout le catalogue »).

**Le client HelloAsso** (`backend/app/services/helloasso.py`) met le jeton
OAuth2 en cache mémoire, protégé par un `threading.Lock` (`:35-41`), avec une
marge de 60 s avant expiration (`:24`, `:108`). Il tente d'abord
`grant_type=refresh_token` et ne retombe sur `client_credentials` qu'à défaut
(`:114-131`) — HelloAsso interdit de redemander un jeton complet à chaque appel
(`CLAUDE.md:831-832`).

---

## 4. Les mécanismes transverses

### 4.1 `services/outbox.py` — la file d'envoi persistante

**Raison d'être** (`backend/app/services/outbox.py:1-14`) : motif *transactional
outbox*. « L'intention d'envoyer est écrite en base au moment du dépôt ; l'envoi
SMTP lui-même est tenté immédiatement, puis repris par un cron en cas d'échec. »

Ce qu'il corrige, textuellement : « avant, l'envoi partait dans un
`BackgroundTask` dont l'exception était avalée. Un SMTP indisponible, un
redémarrage Passenger au mauvais moment ou un mot de passe expiré produisaient le
même résultat — l'utilisateur voyait "Facture envoyée", le comptable ne recevait
rien, et personne ne l'apprenait avant la clôture comptable. »

Et la contrainte qui a fermé les autres options : « **Aucun Celery ni Redis**
: l'hébergement mutualisé O2Switch ne les propose pas » (`:13`).

Mécanique :

| Élément | Où | Justification du code |
|---|---|---|
| `enqueue` | `:58-100` | Sans destinataire configuré, la ligne est **quand même créée** en `pending` avec le motif : « le cron l'enverra dès que la variable sera renseignée, et rien de ce qui a été déposé entre-temps n'est perdu » (`:70-75`) |
| Backoff | `:35-37`, `:149` | 5, 10, 20, 40, 80 min, plafonné à 6 h, puis `abandoned` |
| `_acquire` | `:106-121` | Verrou optimiste par `UPDATE … WHERE status IN (pending, failed)` : « Deux exécutions du cron peuvent se chevaucher […] sans ce verrou, le comptable recevrait la même pièce en double » |
| `reset_stale_locks` | `:162-178` | Au-delà de 15 min (`:39`), un `sending` vient d'un process tué : on le récupère |
| Rechargement des destinataires | `:196-210` | Si la liste avait été figée vide, `_deliver` la recalcule depuis `COMPTA_EMAIL` — « la promesse faite au moment de la mise en file […] ne serait jamais tenue, même après correction de la configuration » |
| Absence de destinataire ≠ échec | `:212-219` | On ne consomme pas de tentative, « sinon la ligne serait abandonnée avant même que le client ait renseigné `COMPTA_EMAIL` » |
| Pièce jointe manquante | `:221-225` | Échec explicite plutôt qu'envoi tronqué |
| `try_send_now` | `:239-254` | Ouvre **sa propre** `SessionLocal` : « appelée depuis un `BackgroundTask`, la session de la requête est déjà fermée » |
| `process_pending` | `:257-292` | Le point d'entrée du cron |
| `reset_for_retry` | `:321-329` | Relance manuelle depuis l'écran comptable |

**Le contrat avec `email._send_raw`** est essentiel :
`EMAIL_ENABLED=false` **lève** désormais (`backend/app/services/email.py:116-130`).
Le commentaire raconte l'incident : « Il retournait auparavant sans rien faire,
"pour que le circuit comptable se déroule jusqu'au bout" — avec pour effet que
`outbox._deliver` marquait la ligne "Envoyée". La production a tourné avec le
drapeau baissé : l'écran des envois affichait tout en vert, et rien ne partait.
Trois semaines sans qu'aucun signal n'existe. Ne rien envoyer reste légitime en
développement ; le dire "envoyé" ne l'est jamais. »

Deux fonctions d'envoi coexistent, et la distinction est délibérée :
`_send_raw` **lève** et est réservé aux envois critiques (`:91-97`) ; `_send` est
best-effort et journalise sans propager (`:163-169`), pour les alertes de stock,
les invitations et les relances de ticket — « un rappel perdu se rattrape au tour
suivant, il n'a pas la criticité d'une pièce comptable » (`:391-392`).

**La reprise** est assurée par `backend/scripts/process_outbound_emails.py`,
lancé toutes les dix minutes par cron (`:3-7`). Le script **sort toujours en
code 0** : « un code d'erreur ferait envoyer un mail d'alerte par cPanel à chaque
exécution, ce qui noierait les vraies anomalies » (`:9-12`). Il fait trois choses :
`outbox.process_pending` (`:132`), `cleanup` des PDF aboutis depuis plus de
30 jours (`:39-67`, « chaque justificatif existe en double »), et
`relancer_les_tickets` (`:70-115`). Ce dernier est greffé ici plutôt que dans un
service dédié parce qu'« un conteneur de plus aurait imposé de recopier
`compose.yml` à la main sur le VPS — étape hors du déploiement automatique »
(`:73-77`). Voir `docs/06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md`.

**Surveillance** : `GET /admin/outbound-emails/etat`
(`backend/app/api/v1/endpoints/admin.py`) expose `EMAIL_ENABLED`, la
configuration SMTP, les destinataires et les compteurs (`outbox.compter`,
`backend/app/services/outbox.py:181-187`). Le besoin est décrit en
`CLAUDE.md:581-584` : « Une file vide et un serveur coupé se ressemblent. »

### 4.2 `services/compta_dispatch.py` — l'orchestration

**Raison d'être** (`backend/app/services/compta_dispatch.py:1-8`) : « Assemble
les trois briques : nomenclature (`naming`), conversion PDF (`pdf`) et file
d'attente persistante (`outbox`). Un justificatif = un PDF = une pièce jointe,
conformément à la demande du client (pas de fusion, pas d'archive ZIP). »

C'est le seul endroit où ces trois services se rencontrent. Les endpoints
facture et note de frais l'appellent avec la même signature
(`prepare_invoice_dispatch` / `prepare_expense_dispatch`), et les corps de
courriel y sont composés à l'identique (`:132-147` et `:197-215`).

Les décisions notables :
- `_outbox_dir` (`:32-33`) place les fichiers sous `OUTBOX_DIR/{entity}/{id}/`,
  **jamais** sous `uploads/` — cf. `backend/app/core/config.py:79-82` : « le
  `.htaccess` laisse passer `/backend/uploads/`, et ces fichiers portent des noms
  prévisibles […] — les y écrire rendrait des factures fournisseur
  téléchargeables sans authentification ».
- `_split_by_size` (`:85-104`) : découpage en plusieurs courriels plutôt
  qu'échec, avec un objet suffixé `(1/3)`, `(2/3)` (`:126`).
- Un justificatif introuvable **ni en base ni sur disque** est journalisé et
  sauté, pas fatal (`:67-72`).

### 4.3 `crud/rattachement.py` — la résolution du rattachement

**Raison d'être** (`backend/app/crud/rattachement.py:1-11`) : « Les factures et
les notes de frais partagent exactement cette règle et alimentent le même circuit
comptable — la résoudre à un seul endroit évite qu'un écran finisse par accepter
ce que l'autre refuse. »

Et la seconde raison, sur le moment de la résolution : « La résolution se fait
**avant toute écriture** : ces champs composent le nom du PDF envoyé au
comptable, et une erreur doit revenir au déposant plutôt que de produire une
pièce mal nommée. »

**Le pôle commande** (`:60-63`) : « Aucune liste de pôles n'est écrite en dur
ici — un pôle créé demain se comporte selon son propre drapeau. » Le drapeau est
`Poles.requiert_evenement` :

| `requiert_evenement` | Ce qui est exigé | Ce qui est refusé | Nom produit |
|---|---|---|---|
| `true` | une catégorie active, **plus** un événement (référentiel ou saisie libre) et sa date | — | `{Pôle}_{Événement}_{date événement}.pdf` |
| `false` | une catégorie active | tout événement | `{Pôle}_{Catégorie}_{date dépense}.pdf` |

La catégorie est résolue **avant** l'aiguillage, pour les deux branches : elle
était auparavant refusée sous un pôle événementiel, si bien que le comptable
n'avait la nature de la dépense que sur la moitié des pièces.

La justification métier du second cas est donnée sur place : « une dépense du
local n'en a pas, et en exiger un obligeait à en inventer » (`:93-94`).

Le résultat est une dataclass gelée `Rattachement`, dont la propriété
`libelle_document` rend l'événement sous un pôle événementiel, la catégorie sous
les autres. Les deux coexistent désormais sur une même pièce et **l'événement
reste prioritaire** : sans quoi les pièces d'un même événement cesseraient de se
ranger ensemble chez le comptable — ce que le nommage sert précisément à
produire.

Deux résolveurs sont délégués :
- `crud.event.resolve_event` (`backend/app/crud/event.py:112-135`) — exactement
  l'un des deux (liste ou saisie libre) ; « La saisie libre est le cas normal pour
  une dépense sans événement HelloAsso […], pas une dégradation » (`:117-119`).
- `crud.expense_category.resolve_for_pole`
  (`backend/app/crud/expense_category.py:174-209`) — refuse une catégorie
  désactivée (`:204-208`), et porte la même justification sur le moment de la
  résolution (`:180-185`).

Note : `date_evenement` vaut `None` sous un pôle sans événement (`:115-117`), ce
qui explique le repli sur `date_depense`/`date_depot` dans `compta_dispatch`.

### 4.4 `core/workflow.py` — le graphe de transitions

**Raison d'être** (`backend/app/core/workflow.py:1-10`) : « Les statuts étaient
auparavant affectés sans aucun contrôle : une note "Remboursée" pouvait repasser
"En attente", et rien n'empêchait de sauter des étapes. Pour des pièces
comptables, cela rend l'historique ininterprétable. Le graphe reste
volontairement permissif sur les corrections […] mais ferme les états
terminaux. »

**Factures** (`:19-27`) :
- `En attente` → `En cours de traitement`, `Validée`, `Refusée`
- `En cours de traitement` → `Validée`, `Refusée`, `En attente`
- `Validée` → ∅ — terminal, « une facture validée est comptabilisée »
- `Refusée` → `En attente`, `En cours de traitement`, `Validée` — ouvert parce
  que « reconnaître une erreur d'appréciation obligeait à repasser par la case
  départ, en deux gestes, sans que rien à l'écran ne l'explique » (`:24-25`)

**Notes de frais** (`:37-48`) :
- `En attente` → `Approuvée`, `Refusée`
- `Approuvée` → `Refusée`, `En attente`
- `Remboursée` → `Approuvée` seulement
- `Refusée` → `En attente`, `Approuvée`

Le point le plus important est une **absence** : « "Remboursée" ne figure dans
AUCUNE cible : ce statut ne se déclare pas, il se constate. On l'atteint par
`POST /reimbursements`, qui enregistre le versement […] et produit le
justificatif. La liste déroulante de l'écran comptable y menait aussi, sans rien
produire : des notes se retrouvaient marquées payées, sans document, et le statut
étant terminal, sans aucun moyen de corriger » (`:31-36`).

La transition `Remboursée → Approuvée` est la porte de sortie de ces notes-là,
et elle est doublement gardée : le graphe l'autorise (`:43`), mais
`crud.expense.validate_expense` la refuse dès qu'un versement est rattaché
(`backend/app/crud/expense.py:275-287`).

Deux garde-fous de conception dans `_check` (`:51-70`) :
- `current == new` passe toujours (`:54-55`) — un enregistrement sans changement
  de statut n'est pas une transition ;
- un statut **inconnu** en base passe aussi (`:57-60`) : « donnée legacy : on
  laisse passer plutôt que de bloquer un utilisateur sur une ligne historique mal
  formée ». C'est une conséquence directe du schéma partagé avec la version
  Streamlit.

Le message d'erreur énumère les transitions possibles et les expose en `extras`
(`:62-70`), ce que le front peut exploiter.

### 4.5 `services/pdf.py` — la conversion PDF

**Raison d'être du choix technique** (`backend/app/services/pdf.py:1-13`) :
« Choix d'`img2pdf` plutôt que Pillow seul : il embarque le flux JPEG **tel
quel** dans le conteneur PDF, sans ré-encodage. Un ticket de caisse photographié
est déjà compressé ; le repasser dans Pillow le recompresserait une seconde fois
et dégraderait la lisibilité des montants — exactement ce qu'un comptable a
besoin de lire. »

`pillow-heif` s'y ajoute pour les photos iPhone, et **doit être enregistré à
l'import** (`:24-32`) : « sans lui, `Image.open` refuse tout HEIC ». L'absence du
paquet ne bloque pas le démarrage, elle dégrade seulement le message d'erreur au
dépôt.

Décisions :

| Élément | Où | Pourquoi |
|---|---|---|
| Gabarit A4 forcé | `:44-50` | « Sans contrainte explicite, img2pdf déduit les dimensions physiques des DPI de l'image : les photos de smartphone n'en déclarent souvent pas, ce qui produit des pages de plusieurs mètres, illisibles à l'impression. » |
| `is_pdf` par magic bytes | `:53-59` | « jamais par l'extension » |
| Ré-encodage **seulement si nécessaire** | `_normaliser_octets`, `:66-109` | Le chemin nominal transmet les octets d'origine. Deux exceptions : orientation EXIF (img2pdf l'ignore, « une photo prise en portrait ressortirait couchée ») et modes RGBA/palette/CMYK, aplatis sur fond blanc |
| Test explicite du tag EXIF | `:80-83`, `:95` | « `ImageOps.exif_transpose` retourne *toujours* une nouvelle instance, y compris sans EXIF. On teste donc explicitement le tag plutôt que l'identité de l'objet, sinon chaque JPEG serait recompressé inutilement. » |
| Une seule implémentation octets/chemin | `:84-87` | « sinon la règle d'orientation finirait par diverger — et une photo couchée dans un PDF ne se voit qu'à la lecture, chez le comptable » |
| `octets_en_pdf` rend un PDF **tel quel** | `:138-156` | « le fichier déposé et le fichier servi sont alors identiques octet pour octet » |
| `ensure_pdf` copie même un PDF | `:186-213` | « la pièce jointe doit porter son nom définitif sur le disque — fastapi-mail nomme l'attachement d'après le fichier, et nos uploads sont des `{uuid}.pdf` » (cf. `backend/app/services/email.py:142-144`) |
| La source n'est jamais modifiée | `:189-190` | « les originaux déposés restent intacts dans `uploads/` » |

### 4.6 `services/files.py` — le stockage des fichiers

**Détection du type par le contenu, jamais par l'extension ni l'en-tête client.**
`_detect_mime` (`:65-84`) traite trois signatures en tête (`:55-59`) puis deux cas
particuliers, expliqués : « **HEIC** est une boîte ISO-BMFF : "ftyp" en 4-8, la
marque en 8-12 ; **WEBP** porte "RIFF" en 0-4 **et** "WEBP" en 8-12 — tester
"RIFF" seul accepterait un WAV ou un AVI » (`:70-73`).

`validate_file_type` (`:97-150`) **refuse tout repli sur le MIME déclaré** :
« il est fourni par le client et se falsifie trivialement. Un fichier arbitraire
renommé en .jpg avec un en-tête `Content-Type: image/jpeg` était accepté tel
quel » (`:118-120`). Le message d'erreur destiné au bénévole est en français
courant et renvoie vers le bouton « Scanner » (`:128-132`) — HEIC était refusé
« sur le geste le plus courant de l'application » (`:30-32`).

**Trois voies d'enregistrement**, selon ce que la donnée exige :

| Fonction | Écrit sur disque ? | En base ? | Pour quoi |
|---|---|---|---|
| `save_upload_file` (`:164-256`) | oui (cache) | oui (`contenu`) | Justificatifs de notes et factures |
| `lire_en_memoire` (`:259-295`) | **non** | oui | Le RIB en document |
| `materialiser` (`:370-393`) | oui, à la demande | lit | Ce qui exige un chemin : conversion PDF, pièces jointes |

`save_upload_file` écrit **par morceaux de 64 Ko** avec un plafond
`MAX_UPLOAD_MB` (`:202-219`), puis relit le fichier pour le stocker en base
(`:221-228`) — « Relecture plutôt qu'accumulation en mémoire pendant le
transfert : l'écriture par morceaux ci-dessus protège des fichiers énormes ».
La base fait autorité : « c'est la seule copie réellement sauvegardée (O2Switch
sauvegarde la base, pas le disque du VPS). L'écriture disque est conservée comme
cache local. »

`convertir_en_pdf=True` (`:165`, `:231-247`) est un **paramètre plutôt qu'une
fonction dédiée** : « le cycle de vie est identique à celui d'un justificatif
normal, seul le format change. Recopier la validation, l'écriture par morceaux et
le garde-fou de taille les ferait diverger » (`:175-178`). Le fichier disque suit
le contenu converti, sinon « `contenu_du_fichier` rendrait une image pour une
ligne dont `type_fichier` annonce un PDF, et `materialiser` donnerait cette image
à `ensure_pdf`, qui la reconvertirait » (`:234-237`).

`lire_en_memoire` existe pour le RIB : « une copie de plus d'une donnée bancaire
est une surface de fuite de plus » (`:263-266`).

**Confinement des chemins.** `_is_inside_uploads` (`:298-310`) garde `delete_file`
et `get_file_path`, avec une justification qui n'a rien d'abstrait :
« `chemin_fichier` provient de la base, mais la base n'est pas une source de
confiance : `POST /admin/database/import` insère des lignes depuis un CSV fourni
par l'utilisateur. Sans ce contrôle, un chemin arbitraire (`/home/user/backend/.env`)
était servi tel quel par `FileResponse`. »

**Lecture.** `contenu_du_fichier` (`:352-367`) sert la base d'abord, le disque en
repli — « Le repli disque couvre les pièces déposées avant la migration, dont la
colonne est vide, et disparaîtra le jour où plus aucune ligne ne sera dans ce
cas. » Les endpoints rendent une `Response` et non une `FileResponse` : « le
contenu vient de la base, il n'y a pas toujours de fichier à pointer »
(`backend/app/api/v1/endpoints/expenses.py:546-564`,
`backend/app/api/v1/endpoints/invoices.py:386-404`).

### 4.7 `services/naming.py` — la nomenclature

Bien que non listé explicitement dans la commande, ce module est indissociable
des précédents.

**Deux séparateurs, volontairement distincts** (`backend/app/services/naming.py:5-10`) :
`_` sépare les composants, `-` remplace tout caractère invalide *à l'intérieur*
d'un composant. « Le comptable peut ainsi re-découper un nom par `split("_")`
sans ambiguïté, ce qui serait impossible si les deux rôles se confondaient. »

**Sortie ASCII pur garantie** (`:12-14`) : « aucun encodage RFC 2231 n'est
nécessaire dans l'en-tête `Content-Disposition`, donc aucun client de messagerie
ne déforme le nom de la pièce jointe. »

`slugify_component` (`:69-108`) retourne `NC` plutôt qu'une chaîne vide — « qui
produirait un `__` cassant le découpage du nom » (`:73-74`) — préfixe les noms
réservés Windows (`:59-63`, `:106-107`), et tronque sur une frontière de mot
(`:97-103`).

`deduplicate_filenames` (`:138-166`) suffixe `-2`, `-3` : « Les justificatifs
d'un même dépôt partagent pôle, événement et date : sans cette passe, les N
pièces jointes porteraient le même nom et les clients de messagerie en
écraseraient certaines. » Pas de « (1) » : « les espaces et parenthèses survivent
mal aux anciennes passerelles SMTP » (`:145-146`). La troncature laisse la place
au suffixe, « sinon […] la collision réapparaîtrait silencieusement » (`:161-164`).

---

## 5. Les modules jumeaux back / front

Trois paires de modules doivent **évoluer ensemble**. Ce n'est pas une
duplication accidentelle : c'est un choix assumé, motivé, et surveillé par les
tests.

### 5.1 `services/naming.py` ↔ `frontend/src/lib/naming.ts`

**Pourquoi la copie existe.** Le front doit afficher au déposant, *avant*
validation, le nom exact que portera sa pièce chez le comptable. Un appel
serveur pour cela ajouterait un aller-retour à chaque frappe.

Le back reste seul juge : « Le backend reste seul juge du nom réellement produit ;
cette copie sert uniquement à montrer au déposant, avant validation, le nom que
portera sa pièce » (`frontend/src/lib/naming.ts:6-9`).

**Pourquoi elles ne divergent pas.** « Les deux implémentations sont couvertes
par la **même table de cas** (`naming.test.ts` / `test_naming.py`) : toute
divergence casse un test » (`frontend/src/lib/naming.ts:9-11`, et
`backend/app/services/naming.py:16-19`). Le module Python est pur précisément
pour pouvoir être testé exhaustivement. Voir `docs/07-TESTS.md`.

**Ce qui doit rester aligné** : la table `EXPLICIT_REPLACEMENTS`
(`naming.py:37-55` / `naming.ts:18-35`), les noms réservés Windows
(`naming.py:59-63` / `naming.ts:39+`), les constantes `MAX_COMPONENT_LEN`,
`MAX_STEM_LEN`, `MISSING` (`naming.py:30-33` / `naming.ts:13-15`), la
translittération NFKD, la troncature et la déduplication.

### 5.2 `core/money.py` ↔ `frontend/src/lib/money.ts`

**Pourquoi** (`backend/app/core/money.py:1-11`) : « le front l'affiche à la
comptabilité, le back le grave dans le justificatif remis et dans
`Remboursements.montant_total`. Une divergence produirait un document
contredisant l'écran qui l'a déclenché. »

La règle commune : `montant − remboursement_deja_emis − remise`, **borné à
zéro** (`backend/app/core/money.py:42-52`, `frontend/src/lib/money.ts:18-27`) —
« un remboursement négatif se lirait comme une dette du bénévole envers
l'association, ce que la donnée ne dit pas ».

**Une asymétrie assumée** : le back travaille en `Decimal` de bout en bout,
jamais en `float`, « la colonne est un `DECIMAL(10,2)`, et `0.1 + 0.2` en virgule
flottante vaut 0.30000000000000004 — un écart qu'une pièce comptable ne peut pas
porter » (`backend/app/core/money.py:12-15`). Le front, lui, est en `number`
JavaScript et compense par `Math.round` sur les conversions en centimes
(`frontend/src/lib/money.ts:29-38`). Les deux doivent rendre le même chiffre sur
les mêmes données ; les représentations internes diffèrent.

Le plafonnement s'applique **par note** dans `total_a_rembourser`
(`backend/app/core/money.py:55-61`) : « une note soldée d'avance ne doit pas
venir amputer le remboursement d'une autre ».

### 5.3 `core/errors.py` ↔ `frontend/src/lib/errors.ts`

Moins souvent cité, mais formalisé dans la procédure d'ajout d'un code :
« 3. Mirror the code in `frontend/src/lib/errors.ts` »
(`backend/app/core/errors.py:18-22`). Le front s'appuie sur le code
(`AUTH_1001`, `RATE_7001`…) pour afficher un message adapté ; un code émis côté
back et inconnu côté front dégrade silencieusement en message générique.

### 5.4 Cas apparenté : `crud/conversation.PORTEE` ↔ `frontend/src/lib/auth.ts`

Ce n'est pas une duplication d'algorithme mais une **duplication de règle
d'accès**, qui doit rester cohérente. Le back définit qui lit quelle boîte
(`backend/app/crud/conversation.py:26-31` : la Compta lit `compta`, le Super
Admin les deux) ; le front décide d'afficher ou non l'écran correspondant via
`ACTIONS.CONVERSATIONS_HANDLE` (`frontend/src/lib/auth.ts:32`, `:71`). Le back
reste la seule autorité (`peut_lire`,
`backend/app/crud/conversation.py:47-50`) ; le front n'évite qu'un écran vide.

### 5.5 Cas apparenté : `core/reimbursement_options.py`

Le contre-exemple délibéré : plutôt que de dupliquer les listes de moyens et
d'établissements, elles sont **servies** au front par
`GET /reimbursements/options`
(`backend/app/api/v1/endpoints/reimbursements.py:43-60`) — « Elles doivent rester
alignées sur ce que l'API accepte : les dupliquer dans le navigateur ferait
diverger les deux au premier ajout » (`:51-53`). Le critère qui distingue les
deux traitements : `naming` et `money` sont des **algorithmes** dont le résultat
doit être affiché sans latence ; les options sont de simples **données**, qu'un
appel suffit à transporter.

---

## 6. Ce que ce document ne dit pas

| Sujet | Où le trouver |
|---|---|
| Tables, colonnes, clés étrangères, migrations Alembic | `docs/02-MODELE-DE-DONNEES.md` |
| Écrans React, TanStack Query, Zustand, routing par rôle | `docs/04-FRONTEND.md` |
| JWT, bcrypt, rate limiting, chiffrement du RIB, sécurité du webhook, matrice de permissions appliquée | `docs/05-SECURITE.md` |
| `.env`, Docker, VPS, cron, tunnel SSH vers O2Switch, `compose.yml` | `docs/06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md` |
| pytest, Vitest, tables de cas partagées `naming`/`money` | `docs/07-TESTS.md` |

### Points non vérifiés lors de la rédaction

- Le contenu exact de `services/email_layout.composer` n'a pas été détaillé ;
  seul son rôle (composer un corps de courriel à partir d'une introduction, de
  blocs libellé/valeur et d'une conclusion) a été observé depuis ses appelants.
- Le parcours inventaire (`stock.py` / `crud/stock.py`, 590 lignes) et le
  parcours import CSV n'ont pas été tracés ; ils ne figuraient pas dans les
  parcours demandés.
- `services/document_scan.py` et `services/openfoodfacts.py` (scanner de
  document, recherche par code-barres) ne sont pas couverts ici.
