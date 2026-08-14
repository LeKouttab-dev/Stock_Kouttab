# 03 — Catalogue des fonctionnalités

Document de référence pour répondre à « est-ce que l'application sait faire X ? ».

Il décrit, pour chaque domaine : ce que l'utilisateur peut faire, qui en a le
droit, les endpoints appelés, l'écran correspondant, et les règles métier qui ne
se devinent pas. Il ne traite ni l'architecture interne, ni le modèle de
données, ni le déploiement, ni les tests.

**Périmètre vérifié** : `backend/app/api/v1/endpoints/*.py`, les modules
`backend/app/crud/*` qui portent les contrôles de rôle, `frontend/src/App.tsx`,
`frontend/src/lib/auth.ts`, `frontend/src/pages/**`, et `CLAUDE.md` §5 et §6.
Les écarts constatés entre la documentation et le code sont signalés au fil du
texte et récapitulés au §15.

**Les quatre rôles** (`frontend/src/lib/constants.ts:1`, `Admins.role` côté
base) : `Benevole`, `AdminBenevoles`, `Compta`, `Super Admin`. Aucune hiérarchie
implicite : `Super Admin` n'hérite pas automatiquement des droits
d'`AdminBenevoles`, chaque endpoint énumère ses rôles. En pratique les listes
usuelles sont `_ADMIN_ROLES = ("AdminBenevoles", "Super Admin")` (stock,
buvette, événements) et `_ACCOUNTANT_ROLES = ("Compta", "Super Admin")` (notes
de frais, factures, tickets, remboursements, file d'envoi).

Préfixe de toutes les routes : `/api/v1`. Authentification par `Authorization:
Bearer <jwt>`, sauf `/auth/*` et le webhook HelloAsso.

---

## 1. Authentification, comptes et profil

### Ce que ça permet

Créer un compte, se connecter, réinitialiser son mot de passe, consulter et
modifier son profil (nom, prénom, courriel, téléphone, IBAN), déposer son RIB
en document.

Un compte créé par inscription libre naît en `pending` : il ne peut rien faire
tant qu'un Super Admin ne l'a pas activé (`app/api/deps.py:34-40` — un compte
`pending` ou `rejected` est refusé sur **toutes** les routes authentifiées).

### Endpoints

| Endpoint | Accès |
|---|---|
| `POST /auth/signup` | public — crée un compte `pending` |
| `POST /auth/login` · `POST /auth/login/json` | public |
| `POST /auth/refresh` · `POST /auth/logout` | public / porteur du refresh token |
| `GET /auth/me` | authentifié |
| `POST /auth/forgot-password` · `GET /auth/reset-password/validate` · `POST /auth/reset-password` | public |
| `GET /auth/validate-invitation?token=&email=` | public |
| `POST /auth/admin-setup` | public, mais exige un token d'invitation valide |
| `GET /users/me/profile` · `PATCH /users/me/profile` | authentifié, sur soi |
| `POST\|GET\|DELETE /users/me/rib-document` | authentifié, sur soi |
| `GET /users/{id}/rib-document` | le propriétaire, `Compta`, `Super Admin` (`users.py:97-98,156`) |

### Écrans

`/login`, `/signup`, `/forgot-password`, `/reset-password`, `/admin-setup`
(pages publiques, `App.tsx:96-100`) ; `/profile` (`ProfilePage.tsx`) et l'onglet
« Profil » de `/expenses` (`MyExpensesPage.tsx:111`), qui affichent le même
formulaire.

### Règles métier

- **Le contrôle du RIB porte sur le rôle *et* sur la propriété.** Un bénévole
  qui devine l'identifiant d'un collègue ne récupère pas ses coordonnées
  bancaires (`users.py:144-161`). Même règle que `_can_see_rib` côté notes de
  frais (`expenses.py:77-80`).
- **L'IBAN est chiffré au repos** (AES-256-GCM, colonne `ChampChiffre`). Rien à
  faire côté application, mais la perte de `RIB_ENCRYPTION_KEY` rend les IBAN
  définitivement illisibles.
- L'IBAN du profil sert au virement, le **RIB en document** sert de preuve : ce
  sont deux champs distincts, les deux protégés par la même règle d'accès.
- `GET /users/{id}/rib-document` est bien appelé par l'écran comptable
  (`ValidateExpensesPage.tsx:499`), pas par l'écran de profil.

---

## 2. Stock local, catégories et sous-catégories

### Ce que ça permet

Parcourir l'inventaire par catégorie puis sous-catégorie, consulter les
quantités et les seuils d'alerte. Selon le rôle : modifier directement une
quantité, ou **demander** une modification qu'un administrateur approuvera.
Créer, renommer, supprimer articles, catégories et sous-catégories. Importer un
inventaire par CSV.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Consulter articles / catégories / sous-catégories | ✅ | ✅ | ✅ | ✅ |
| Demander une modification de quantité | ✅ | ✅ * | ✅ * | ✅ * |
| Modifier une quantité directement | — | ✅ | — | ✅ |
| Approuver / refuser une demande | — | ✅ | — | ✅ |
| CRUD articles, catégories, sous-catégories | — | ✅ | — | ✅ |
| Import CSV d'inventaire | — | ✅ | — | ✅ |
| Voir les demandes des autres | — | ✅ | — | ✅ |

\* Côté serveur, `POST /stock/modifications` est ouvert à tout compte
authentifié : un administrateur peut déposer une demande « pour la traçabilité »
(`stock.py:405-408`). Côté écran, le bouton n'est proposé qu'au `Benevole`
(`ACTIONS.STOCK_REQUEST_MOD`, `lib/auth.ts:41`).

### Endpoints

- Articles : `GET /stock/items` (filtres `categorie`, `sous_categorie`,
  `only_alerts`), `POST /stock/items`, `PATCH /stock/items/{id}`,
  `PUT /stock/items/{id}/quantity`, `DELETE /stock/items/{id}`,
  `POST /stock/items/import-csv?skiprows=` — tout sauf `GET` réservé à
  `_ADMIN_ROLES`.
- Catégories : `GET`/`POST /stock/categories`, `PATCH`/`DELETE
  /stock/categories/{name}`.
- Sous-catégories : `GET /stock/subcategories?category=`, `POST`, `PATCH`/`DELETE
  /stock/subcategories/{id}`.
- Statistiques et alertes : `GET /stock/statistics`, `GET /stock/low-stock`,
  `POST /stock/low-stock/notify` (`_ADMIN_ROLES`).
- Workflow : `GET /stock/modifications?status=&days=`,
  `POST /stock/modifications`, `POST /stock/modifications/{id}/approve`,
  `POST /stock/modifications/{id}/refuse`.
- Codes-barres : `GET /stock/items/by-barcode/{barcode}`,
  `GET /stock/lookup-barcode/{barcode}`.

### Écrans

`/stock` → `/stock/:category` → `/stock/:category/:subcategory`
(`StockCategoriesPage`, `StockSubCategoriesPage`, `StockItemsPage`), avec les
modales `DirectModificationModal`, `RequestModificationModal`,
`AddItemFromBarcodeModal`. Le CRUD de référentiel et la file des demandes sont
sur `/admin` (`AddItemSection`, `ImportCsvSection`,
`CategoriesManagementSection`, `SubCategoriesManagementSection`,
`PendingStockModsSection`). Le tableau de bord `/dashboard` porte les onglets
Vue d'ensemble, Historique, Alertes, Modifications.

### Règles métier

- **Un bénévole ne voit que ses propres demandes.** `GET /stock/modifications`
  filtre la liste pour les non-administrateurs (`stock.py:394-395`) : la liste
  complète exposait à tout compte authentifié l'activité de tout le monde.
- `PATCH /stock/items/{id}` refuse tout rôle hors `_ADMIN_ROLES`, y compris pour
  une simple quantité (`stock.py:102-105`) : la voie ouverte aux autres est la
  demande de modification.
- Une baisse de quantité sous le seuil déclenche une alerte par courriel, une
  seule fois (drapeau `alert_sent`).
- `GET /stock/lookup-barcode/{barcode}` cherche d'abord dans le stock, puis dans
  la buvette, puis interroge OpenFoodFacts — et renvoie **toujours** le résultat
  OpenFoodFacts quand il existe, même en cas de trouvaille locale, pour que
  l'écran puisse proposer de rafraîchir les métadonnées (`stock.py:186-220`).

### Écarts constatés

- **`POST /stock/alert` n'existe pas au back.** Le front l'appelle
  (`frontend/src/api/endpoints/stock.ts:153`, via `useSendStockAlert`, utilisé
  par `pages/dashboard/tabs/AlertsTab.tsx:21`). La route réelle est
  `POST /stock/low-stock/notify` (`endpoints/stock.py:362`) et elle renvoie un
  `MessageOut`, pas `{ recipients, items }`. Le bouton d'envoi des alertes de
  l'onglet « Alertes » part donc en 404.
- `GET /stock/items/by-barcode/{barcode}` et `PUT /stock/items/{id}/quantity`
  n'ont aucun appelant côté front : le scanner passe par `lookup-barcode` et
  l'édition par `PATCH /stock/items/{id}`.

---

## 3. Notes de frais

### Ce que ça permet

Un bénévole saisit une dépense (date, montant, fournisseur, pôle, rattachement,
nature de charge, remise, remboursement déjà émis) et y joint ses tickets. Il
suit l'avancement de ses demandes, peut corriger une note tant qu'elle est « En
attente », et ajouter un justificatif oublié. La comptabilité valide, refuse,
commente, écarte une pièce illisible, archive les notes soldées, et rembourse
(cf. §5).

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Soumettre une note | ✅ | ✅ | ✅ | ✅ |
| Voir ses notes (`/expenses/me`) | ✅ | ✅ | ✅ | ✅ |
| Voir toutes les notes (`GET /expenses`) | — | — | ✅ | ✅ |
| Éditer sa note « En attente » | ✅ | ✅ | ✅ | ✅ |
| Éditer **n'importe quelle** note, à **n'importe quel** statut | — | — | ✅ | ✅ |
| Changer le statut + commentaire compta | — | — | ✅ | ✅ |
| Voir l'IBAN du déposant | — | — | ✅ | ✅ |
| Ajouter une pièce à une note existante | ✅ (la sienne, non remboursée) | idem | ✅ (toute note) | ✅ |
| Écarter / rétablir une pièce | — | — | ✅ | ✅ |
| Archiver / restaurer une note | — | — | ✅ | ✅ |
| Supprimer définitivement | — | — | — | ✅ |
| Relancer l'envoi au comptable | — | — | ✅ | ✅ |

### Endpoints

| Endpoint | Accès |
|---|---|
| `GET /expenses/me` | authentifié — éteint la pastille du déposant |
| `GET /expenses?include_archived=` | `_ACCOUNTANT_ROLES` |
| `POST /expenses` (multipart, ≤ 5 fichiers) | authentifié |
| `PATCH /expenses/{id}` | propriétaire si « En attente », sinon `_ACCOUNTANT_ROLES` (`crud/expense.py:228-233`) |
| `PATCH /expenses/{id}/validate` | `_ACCOUNTANT_ROLES` |
| `DELETE /expenses/{id}` — **archive** | `Compta`, `Super Admin` (`crud/expense.py:337`) |
| `POST /expenses/{id}/restore` | `Compta`, `Super Admin` (`crud/expense.py:415`) |
| `DELETE /expenses/{id}/definitif` (motif obligatoire) | `Super Admin` seul (`crud/expense.py:365`) |
| `GET /expenses/{id}/files` | propriétaire ou `_ACCOUNTANT_ROLES` |
| `POST /expenses/{id}/files` | cf. `peut_deposer_une_piece` (`crud/expense.py:490-500`) |
| `DELETE /expenses/{id}/files/{file_id}` — **écarte**, motif obligatoire | `Compta`, `Super Admin` |
| `POST /expenses/{id}/files/{file_id}/restore` | `Compta`, `Super Admin` |
| `GET /expenses/{id}/files/{file_id}` | propriétaire ou `_ACCOUNTANT_ROLES` |
| `POST /expenses/{id}/resend-compta-email` | `_ACCOUNTANT_ROLES` |

### Écrans

Tout tient sur `/expenses` (`MyExpensesPage.tsx`), en onglets :
« Soumettre » · « Mes demandes » · « Remboursements » · « Valider » (visible
seulement si `ACTIONS.EXPENSES_VALIDATE`) · « Profil ».
L'onglet « Valider » est `ValidateExpensesPage.tsx`, avec les modales
`EcartJustificatifModal`, `ReimbursementModal`, `SuppressionDefinitiveModal`.
L'ancienne URL `/expenses/validate` redirige vers `/expenses#valider`
(`App.tsx:119-122`).

### Règles métier

- **Statuts** : `En attente` → `Approuvée` → `Remboursée`, plus `Refusée`.
  Transitions contrôlées par `core/workflow.py:EXPENSE_TRANSITIONS`.
- **`Remboursée` ne se déclare pas.** Le statut ne figure comme cible d'aucune
  transition : il est posé par `POST /reimbursements`, qui enregistre le
  versement et produit le justificatif. Tenter de le poser à la main renvoie un
  message explicite (`crud/expense.py:291-301`).
- **Retour arrière depuis `Remboursée`** : autorisé vers `Approuvée`, mais
  **seulement tant qu'aucun versement n'est rattaché** (`id_remboursement is
  None`, `crud/expense.py:275-287`). C'est la porte de sortie des notes marquées
  à tort par l'ancienne liste déroulante ; une note soldée par un versement réel
  est verrouillée, parce que son justificatif est déjà émis.
- **Un refus se rouvre** : `Refusée` → `En attente` **ou** `Approuvée`, en un
  seul geste (`core/workflow.py`).
- **Archiver n'est pas supprimer.** `DELETE /expenses/{id}` pose `archived_at` /
  `archived_by` ; la ligne et ses justificatifs restent en base et se restaurent.
  **Seule une note « Remboursée » s'archive** (`crud/expense.py:342`) : ranger
  une note en cours de traitement la sortirait des listes alors que le bénévole
  attend encore son argent.
- **Les archives sont exclues par défaut** des deux côtés : côté déposant
  toujours (`crud/expense.py:83`), côté comptabilité sauf
  `?include_archived=true` (`crud/expense.py:120`).
- **Écarter un justificatif** le sort du dossier **et du circuit comptable**
  (`compta_dispatch` l'ignore), sans le retirer de la base. Le geste est
  réversible et **le motif est obligatoire** : il est montré au déposant, qui
  doit savoir ce qu'on lui reproche, faute de quoi il redépose la même pièce
  (`crud/expense.py:426-462`). Écarter allume la pastille du déposant.
- **Ajouter une pièce** : le déposant tant que sa note n'est pas
  « Remboursée » (au-delà, le versement est parti et son justificatif est émis) ;
  la comptabilité à tout moment (`crud/expense.py:490-500`).
- **Suppression définitive** : `Super Admin` seul, motif obligatoire,
  journalisée. Emporte les justificatifs et, si le versement qui soldait la note
  se retrouve sans aucune note, ce versement aussi. Réservée au ménage — notes
  de test, saisies fautives —, jamais à une pièce comptable réelle.
- **Suivi du déposant** : `Expense.non_lu_demandeur` s'allume à **toute** décision
  de la comptabilité, statut **ou** commentaire seul, et s'éteint quand le
  déposant ouvre `GET /expenses/me` — après sérialisation des lignes, sinon
  l'écran qui vient d'allumer la pastille ne la montrerait jamais
  (`expenses.py:126-131`).
- **Le courriel de statut ne ment plus** : un commentaire seul n'annonce plus
  « votre note a été approuvée ». Objet et corps changent selon que le statut a
  bougé ou non (`expenses.py:339-352`). Il passe par la file `outbox`, comme les
  envois comptables.
- **Filtres de l'écran comptable** : À traiter · Approuvées · Remboursées ·
  Archivées · Toutes, chacun portant son compte, ouverture sur « À traiter »
  (`ValidateExpensesPage.tsx:70-84`).

### Écart constaté

`POST /expenses/{id}/resend-compta-email` existe côté API mais **n'a aucun
écran** : seul l'équivalent facture est câblé (`api/endpoints/invoices.ts:74`).

---

## 4. Factures

### Ce que ça permet

Déposer une ou plusieurs pièces (jusqu'à 10 fichiers) rattachées à un pôle et à
un événement ou une catégorie, avec fournisseur, montant et commentaire
facultatifs. Suivre le traitement. La comptabilité change le statut avec motif,
archive, restaure, relance l'envoi au comptable.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Déposer | ✅ | ✅ | ✅ | ✅ |
| Voir ses factures | ✅ | ✅ | ✅ | ✅ |
| Voir toutes les factures | — | — | ✅ | ✅ |
| Changer le statut + `commentaires_compta` | — | — | ✅ | ✅ |
| Archiver | ✅ (les siennes, « En attente » seulement) | ✅ (idem) | ✅ (toutes, tout statut) | ✅ |
| **Restaurer** | — | — | ✅ | ✅ |
| Télécharger une pièce | ✅ (les siennes) | ✅ (les siennes) | ✅ | ✅ |
| Relancer l'envoi au comptable | — | — | ✅ | ✅ |

### Endpoints

`GET /invoices/me`, `GET /invoices` (filtres `status`, `days`, `search`,
`include_archived`), `POST /invoices` (multipart), `PATCH /invoices/{id}/status`,
`DELETE /invoices/{id}` (archive), `POST /invoices/{id}/restore`,
`GET /invoices/{id}/files/{file_id}`,
`POST /invoices/{id}/resend-compta-email`.

### Écrans

`/invoices/upload` (`InvoiceUploadPage.tsx`, dépôt + scanner + rappel des
justificatifs demandés) et `/invoices` (`InvoiceListPage.tsx`, liste filtrée par
vues À traiter / Archivées / Toutes, changement de statut, archivage, relance
d'envoi, et la section « Demandes de justificatif »).

### Règles métier

- **Champs obligatoires au dépôt** : `id_pole`, et selon le pôle un événement ou
  une catégorie (cf. §6). Au moins un fichier, dix au maximum
  (`invoices.py:149-156`).
- **Transitions** (`core/workflow.py:INVOICE_TRANSITIONS`) :
  `En attente` → `En cours de traitement` / `Validée` / `Refusée` ;
  `En cours de traitement` → `Validée` / `Refusée` / `En attente` ;
  **`Validée` est terminal** (la facture est comptabilisée) ;
  `Refusée` se revoit vers `En attente`, `En cours de traitement` ou `Validée`.
- **Un refus porte un motif** : `PATCH /invoices/{id}/status` accepte
  `commentaires_compta`, repris dans le courriel envoyé au déposant.
- **Le déposant n'archive que ce qui n'est pas parti au traitement**, c'est-à-dire
  « En attente » (`crud/invoice.py:177-186`). La comptabilité archive à tout
  statut. **La restauration est réservée à la comptabilité**
  (`crud/invoice.py:198`).
- **Les filtres s'appliquent aussi au déposant** : `GET /invoices` les
  transmet à `list_invoices_for_user` (`invoices.py:118-123`). Ils étaient
  ignorés pour lui, si bien que le menu déroulant de son écran ne faisait rien.
- Les listes du déposant excluent les archives sans exception
  (`crud/invoice.py:80-95`).
- `Invoice.non_lu_demandeur` suit le même patron que côté notes de frais : il
  s'éteint à l'ouverture de `GET /invoices/me`.

### Écart avec `CLAUDE.md` §5

La ligne « Factures — archiver / restaurer | ✅ (les siennes, « En attente ») »
attribue au bénévole les deux gestes. **Restaurer est réservé à `Compta` et
`Super Admin`.**

---

## 5. Remboursements groupés

### Ce que ça permet

La comptabilité rembourse **un bénévole**, pas une note : un versement solde
plusieurs dépenses approuvées et produit un justificatif unique (PDF + tableur),
calqué sur le modèle « NDF - Nom Prénom ». Le bénévole consulte ses
remboursements et télécharge la preuve.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Enregistrer un versement | — | — | ✅ | ✅ |
| Voir les fiches et totaux dus par bénévole | — | — | ✅ | ✅ |
| Lire les moyens / établissements du formulaire | — | — | ✅ | ✅ |
| Consulter la liste des remboursements | ✅ (les siens) | ✅ (les siens) | ✅ (tous) | ✅ (tous) |
| Télécharger le justificatif PDF / XLSX | ✅ (les siens) | ✅ (les siens) | ✅ | ✅ |

### Endpoints

- `GET /reimbursements` — tous pour la comptabilité, les siens sinon
  (`reimbursements.py:83-87`).
- `POST /reimbursements` — `_ACCOUNTANT_ROLES`.
- `GET /reimbursements/by-volunteer` — `_ACCOUNTANT_ROLES`.
- `GET /reimbursements/options` — `_ACCOUNTANT_ROLES`, listes **figées** servies
  par `core/reimbursement_options.py` plutôt que recopiées côté front.
- `GET /reimbursements/{id}/document?format=pdf|xlsx` — comptabilité ou
  **bénévole concerné** (`reimbursements.py:126-130`).

### Écrans

Onglet « Remboursements » de `/expenses` (`ReimbursementsList.tsx`) pour la
consultation et le téléchargement ; `ReimbursementModal.tsx` depuis l'onglet
« Valider » pour enregistrer un versement. Une note « Remboursée » renvoie
directement vers son versement.

### Règles métier

1. **Tout ou rien** (`crud/reimbursement.py:129-190`). Un lot est refusé **en
   bloc, avant toute écriture**, si : la sélection est vide, une note est
   introuvable, les notes appartiennent à **plusieurs bénévoles**, une note est
   **déjà rattachée à un versement**, ou une note n'est pas « Approuvée ».
   Rembourser trois notes sur quatre en silence ne se verrait qu'au
   rapprochement bancaire.
2. **`montant_total` est un instantané** : figé à l'enregistrement. Le
   recalculer ferait bouger un chiffre déjà justifié si une note était corrigée
   ensuite.
3. Les documents sont produits dans `OUTBOX_DIR`, **hors de `uploads/`** (leurs
   noms sont prévisibles), **et stockés en base** (`contenu_pdf`,
   `contenu_xlsx`). La base fait autorité, le disque n'est qu'un cache utile à
   la file d'envoi.
4. **Deux envois distincts** sont mis en file : un vers la comptabilité, un vers
   le bénévole. Il ne recevait rien auparavant : il apprenait son remboursement
   sur son compte bancaire, sans pièce à produire, alors que le document porte
   son nom.
5. Les valeurs par défaut de moyen, établissement et approbateur viennent du
   serveur (`GET /reimbursements/options`).

---

## 6. Rattachement d'une pièce : événement ou catégorie

Règle transverse aux factures **et** aux notes de frais, résolue une seule fois
dans `crud/rattachement.py` — dupliquer la règle finirait par faire diverger ce
que l'un accepte et ce que l'autre refuse.

**Le pôle décide, et lui seul.** Aucune liste de pôles n'est écrite en dur, ni
au back ni au front : un pôle créé demain se comporte selon son propre drapeau
`requiert_evenement`.

| `Poles.requiert_evenement` | Le dépôt exige | Nom du PDF comptable |
|---|---|---|
| `true` (EV(T), EV(G), EV(J)) | un **événement** — du référentiel ou saisi librement — **et** sa date | `{Pôle}_{Événement}_{date événement}.pdf` |
| `false` (Frais généraux, Institut, Halaqa, Séjour annuel) | une **catégorie** de dépense et une description | `{Pôle}_{Catégorie}_{date dépense}.pdf` |

Autres règles :

- Fournir une catégorie sous un pôle événementiel est **refusé** avec un message
  explicite, et réciproquement (`crud/rattachement.py:66-73`).
- Sous un pôle événementiel, la **date de l'événement est obligatoire**.
- Les pôles EV portent une **famille** (`Poles.type_evenement` : `T`, `G`, `J`)
  et ne proposent que les événements de la leur (`Events.type_ev`). Cette
  famille se renseigne à la main — HelloAsso ne la connaît pas — et un événement
  **non classé reste proposé sous tous les pôles EV** : filtrer strictement
  viderait les listes au lendemain de chaque synchronisation.
- Une dépense du local (courses, goûter, matériel) n'a pas d'événement : en
  exiger un obligeait le déposant à en inventer, et le comptable recevait des
  pièces rattachées à des événements fictifs.
- La résolution se fait **avant toute écriture** : elle compose le nom du fichier
  envoyé au comptable, et une erreur doit revenir au déposant plutôt que
  produire une pièce mal nommée.

---

## 7. Circuit comptable et file d'envoi

### Ce que ça permet

Au dépôt d'une facture ou d'une note de frais accompagnée de justificatifs,
chaque pièce est convertie en PDF A4, nommée selon la nomenclature comptable, et
mise en file vers le service comptable. La comptabilité supervise cette file :
elle voit ce qui est parti, ce qui a échoué, et relance.

### Endpoints

- `GET /admin/outbound-emails?status=&limit=` — `Compta`, `Super Admin`.
- `GET /admin/outbound-emails/etat` — santé du circuit : `EMAIL_ENABLED`, SMTP
  configuré, destinataires, compteurs en attente / en échec.
- `POST /admin/outbound-emails/{id}/retry` — `Compta`, `Super Admin`.

### Écran

Section « Envois comptables » de `/admin` (`OutboundEmailsSection.tsx`), visible
si `ACTIONS.COMPTA_RESEND_EMAIL` (`Compta`, `Super Admin`).

### Règles métier

1. Pôle et événement sont résolus **avant** toute écriture (cf. §6).
2. Chaque justificatif est converti en PDF A4 (`services/pdf.py`) et nommé
   `{Pôle}_{Événement}_{AAAA-MM-JJ}.pdf` (`services/naming.py`), avec suffixe
   `-2`, `-3` en cas de collision.
3. L'envoi est inscrit dans `OutboundEmails` **dans la transaction du dépôt**,
   puis tenté immédiatement en tâche de fond. La conversion PDF, elle, est
   synchrone : un échec doit remonter au déposant, pas disparaître.
4. **`EMAIL_ENABLED=false` fait échouer l'envoi**, il ne le fait pas passer pour
   réussi. La production a tourné jusqu'au 2026-08-13 avec un écran tout en vert
   et des boîtes vides. Ne rien envoyer reste légitime en développement ; le
   dire « envoyé » ne l'est jamais.
5. En cas d'échec : backoff 5 / 10 / 20 / 40 / 80 minutes, puis `abandoned`. Le
   cron `scripts/process_outbound_emails.py` reprend la file toutes les 10
   minutes.
6. Les PDF prêts à l'envoi vont dans `OUTBOX_DIR`, **hors de `uploads/`**, parce
   que leurs noms sont prévisibles.
7. `frontend/src/lib/naming.ts` duplique `services/naming.py` pour montrer au
   déposant le nom exact qui partira ; les deux modules partagent la même table
   de cas de test. Même relation entre `app/core/money.py` et
   `frontend/src/lib/money.ts`.
8. `GET /admin/outbound-emails/etat` existe parce qu'une file vide et un serveur
   coupé se ressemblent : sans ce signal, il faut déposer une pièce pour
   découvrir que rien ne part.

---

## 8. Tickets de justificatif

### Ce que ça permet

La comptabilité constate un achat sans facture et ouvre une demande nommant le
bénévole, avec libellé (seul champ obligatoire), montant attendu, date d'achat,
fournisseur et description. Le bénévole reçoit des relances par courriel et
retrouve la demande dans l'application. La comptabilité relance à la demande,
clôt ou annule, en rattachant éventuellement la facture reçue.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Voir ce qu'on me demande (`GET /tickets/me`) | ✅ | ✅ | ✅ | ✅ |
| Lister tous les tickets | — | — | ✅ | ✅ |
| Ouvrir, modifier, relancer, clore | — | — | ✅ | ✅ |
| Lister les destinataires possibles | — | — | ✅ | ✅ |

### Endpoints

`GET /tickets?statut=`, `POST /tickets`, `PATCH /tickets/{id}`,
`POST /tickets/{id}/close`, `POST /tickets/{id}/remind`,
`GET /tickets/destinataires` — tous `_ACCOUNTANT_ROLES` ;
`GET /tickets/me` — tout utilisateur authentifié.

### Écrans

`TicketsManagementSection` sur `/invoices` (côté comptabilité) ;
`MesJustificatifsDemandes` sur `/invoices/upload` (côté bénévole,
`InvoiceUploadPage.tsx:162`).

### Règles métier

- **Cadence : une relance tous les 3 jours, 5 fois au maximum**
  (`DELAI_ENTRE_RAPPELS = timedelta(days=3)`, `RAPPELS_MAX = 5`,
  `crud/ticket.py:31-32`).
- **Un ticket jamais relancé l'est immédiatement** : le premier rappel part à
  l'ouverture (`tickets.py:114-116`), mais peut échouer — sans ce rattrapage,
  une demande ouverte un vendredi soir resterait muette tout le week-end.
- **Passé le quota, le ticket reste ouvert mais se tait.** Un rappel reçu dix
  fois finit en filtre, et emporte les suivants.
- **La relance manuelle ne consomme pas le quota** (`compter=False`,
  `tickets.py:189`) : c'est un geste délibéré, pas une relance programmée. Elle
  est refusée sur un ticket clos, et sur un bénévole sans adresse de messagerie.
- **La clôture est manuelle, le rattachement de la facture aussi.** Deviner
  qu'une pièce déposée correspond à un ticket le fermerait dès que le bénévole
  dépose autre chose, et les relances cesseraient alors que la pièce attendue
  manque toujours.
- **Clore supprime le ticket**, au lieu de l'archiver comme une note ou une
  facture. L'écran de la comptabilité affichait les demandes closes à la suite
  des ouvertes, indéfiniment : personne ne les relisait, et la pièce reçue est
  au dossier de toute façon. Une seconde clôture répond donc 404, et une
  fermeture par erreur se rattrape en rouvrant une demande — pas en restaurant
  l'ancienne.
- `GET /tickets/destinataires` est un endpoint distinct de `GET /users`
  (réservé au Super Admin) et ne renvoie **que l'identifiant et le nom complet**
  — ni adresse, ni rôle, ni téléphone — et **seulement les comptes actifs**
  (`tickets.py:47-64`).
- Les relances programmées sont portées par
  `scripts/process_outbound_emails.py`, devenu « file d'envoi et relances
  programmées » : un service dédié aurait imposé de recopier `compose.yml` à la
  main sur le VPS.
- Statuts : `ouvert` · `clos` · `annule`.

### Écart constaté

`TicketsManagementSection` est rendu **sans aucune garde de rôle** sur
`/invoices` (`InvoiceListPage.tsx:116`), page ouverte à tout compte
authentifié. Un `Benevole` ou un `AdminBenevoles` voit la carte « Demandes de
justificatif » et son bouton « Demander », alors que `GET /tickets`,
`GET /tickets/destinataires` et `POST /tickets` lui répondent 403.

---

## 9. Conversations — espace de contact

### Ce que ça permet

Ouvrir un fil de discussion adressé à la comptabilité ou à l'administration,
échanger des messages, suivre l'état de sa demande. L'équipe traite les fils qui
lui sont adressés, change leur statut, et réoriente un fil mal adressé.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Ouvrir un fil, lister les siens, y répondre | ✅ | ✅ | ✅ | ✅ |
| Boîte de l'équipe (`GET /conversations/equipe`) | liste vide | liste vide | ✅ (`compta`) | ✅ (`compta` + `admin`) |
| Changer le statut d'un fil | — | — | ✅ (les siens de portée) | ✅ (les deux boîtes) |
| Réorienter un fil (`PATCH .../destinataire`) | — | — | ✅ * | ✅ |

\* Voir l'écart signalé plus bas.

**Portée** (`crud/conversation.py:28-31`) : `Compta` → `compta` ; `Super Admin` →
`compta` et `admin`. `Benevole` et `AdminBenevoles` n'ont **aucune** portée
d'équipe.

### Endpoints

`POST /conversations`, `GET /conversations`, `GET /conversations/equipe?statut=`,
`GET /conversations/{id}`, `POST /conversations/{id}/messages`,
`PATCH /conversations/{id}/statut`, `PATCH /conversations/{id}/destinataire` —
tous derrière `get_current_user`, les contrôles fins sont dans le CRUD.

### Écran

`/contact` (`ContactPage.tsx`), onglets « Mes fils » · « Nouvelle
conversation » · « Boîte de l'équipe » (ce dernier visible si
`ACTIONS.CONVERSATIONS_HANDLE`, soit `Compta` et `Super Admin`).
Le fil lui-même : `ConversationThread.tsx`.

### Règles métier

- **Un rôle sans portée reçoit une liste vide, pas un refus** : même parti que
  les compteurs de notification — l'interface n'a pas à distinguer « rien à
  traiter » de « pas concerné » (`contact.py:148-153`).
- **Un fil se lit par son auteur, par l'équipe de sa portée, et par personne
  d'autre.** Une question de remboursement porte sur des montants, parfois sur
  un différend.
- **Ouvrir un fil éteint la pastille du demandeur** (`marquer_lu`,
  `contact.py:167`).
- **L'auteur n'est jamais saisi** : le serveur reprend l'identité du compte
  connecté. Un champ « votre nom » se remplit de n'importe quoi.
- **Le destinataire est un mot-clé (`compta` / `admin`), pas une adresse.**
  Accepter une adresse ferait de cet endpoint un relais de courriel ouvert. Les
  adresses réelles sont résolues côté serveur (`contact.py:53-57`).
- **Répondre sur un fil `traitee` le rouvre.** Sans cela, une précision demandée
  après coup ne serait jamais lue : le fil est rangé, plus personne ne le
  regarde.
- **Passer un fil à `traitee` allume la pastille du demandeur** : il doit
  apprendre que sa question est close, sans quoi il attendrait une réponse qui
  ne viendra plus (`crud/conversation.py:170-172`).
- `auteur_nom` et `de_l_equipe` sont **figés à l'écriture** de chaque message :
  un compte supprimé laisserait des messages anonymes, et un bénévole promu
  comptable ferait passer ses anciennes questions pour des réponses.
- `attente_equipe` et `non_lu_demandeur` sont **dénormalisés** sur le fil : ce
  sont exactement les deux questions que posent les pastilles à chaque
  chargement de page.
- **Le courriel prévient seulement** : le fil est déjà enregistré quand
  `outbox.enqueue` est appelé. Un SMTP en panne retarde un avis, il ne fait plus
  perdre la question.
- **Pas de temps réel** : le fil se recharge à chaque envoi. Une question de
  bénévole se traite dans la journée, pas à la seconde.
- Statuts : `ouverte` · `en_cours` · `traitee`.

### Écart constaté

La docstring de `crud/conversation.transferer` (`conversation.py:181-186`)
annonce « le Super Admin seul », mais le contrôle effectif est
`conversation.destinataire not in portee_de(user)` (`conversation.py:191`) : un
`Compta` **peut** réorienter vers l'administration un fil qui lui est adressé.
Il ne peut pas récupérer un fil `admin`, en revanche.

---

## 10. Utilisateurs, invitations et annuaire

### Ce que ça permet

Le Super Admin valide ou rejette les inscriptions, change les rôles, supprime
des comptes, et invite par courriel de nouveaux administrateurs. La comptabilité
consulte un annuaire en lecture seule.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Lister les comptes (`GET /users`) | — | — | — | ✅ |
| Lister les comptes en attente | — | — | — | ✅ |
| Valider / rejeter un compte | — | — | — | ✅ |
| Changer un rôle | — | — | — | ✅ |
| Supprimer un compte | — | — | — | ✅ |
| Annuaire en lecture seule (`GET /users/annuaire`) | — | — | ✅ | ✅ |
| Créer / lister / révoquer une invitation | — | — | — | ✅ |

### Endpoints

`GET /users`, `GET /users/pending`, `PATCH /users/{id}/validate`,
`PATCH /users/{id}/role`, `DELETE /users/{id}` — `Super Admin` ;
`GET /users/annuaire` — `Compta`, `Super Admin` ;
`GET /invitations`, `POST /invitations`, `DELETE /invitations/{id}`,
`POST /invitations/cleanup` — `Super Admin`.

### Écrans

Sections de `/admin` : `PendingUsersSection`, `UsersManagementSection`,
`InvitationsSection` (définie dans `AdminPage.tsx:131`), `AnnuaireSection`.
Les trois premières ne s'affichent que si `ACTIONS.ADMIN_VALIDATE_USERS`
(Super Admin) ; `AnnuaireSection` si `ACTIONS.COMPTA_RESEND_EMAIL`
(`Compta`, `Super Admin`) — `AdminPage.tsx:45-50, 113`.

### Règles métier

- **Un compte `pending` ou `rejected` ne peut rien faire** : le refus est posé
  au niveau de la dépendance d'authentification, avant tout endpoint
  (`deps.py:34-40`).
- **« Rejeter » supprime réellement le compte** (`users.py:170-178`) : le statut
  `rejected` renvoyé n'est qu'une réponse de forme.
- **`GET /users` exclut le demandeur** de la liste (`users.py:35`) : on ne se
  gère pas soi-même depuis cet écran.
- **L'annuaire n'expose pas l'IBAN** : il renvoie `UserOut`, pas
  `UserDetailOut`. « Cet écran est un annuaire, pas un fichier de coordonnées
  bancaires » (`users.py:44-53`). Il est en lecture seule : les actions (rôles,
  suppression) restent sur `GET /users`, fermé au Super Admin.
- Les invitations portent un `token_hash` SHA256, une expiration, un compteur de
  tentatives et un drapeau `used`.
- `POST /auth/admin-setup` crée le Super Admin initial à partir d'un token
  d'invitation.

### Écart constaté

`POST /invitations/cleanup` (`invitations.py:76-81`) n'a aucun appelant côté
front.

---

## 11. Référentiels : pôles, événements, catégories de dépense

### Ce que ça permet

Administrer les listes qui alimentent les formulaires de dépôt : pôles (avec
leur drapeau `requiert_evenement` et leur famille `type_evenement`), événements
(synchronisés depuis HelloAsso ou saisis à la main), catégories de dépense.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Lire les pôles / événements / catégories de dépense | ✅ | ✅ | ✅ | ✅ |
| CRUD **pôles** | — | — | — | ✅ |
| CRUD **catégories de dépense** | — | — | — | ✅ |
| CRUD **événements** | — | ✅ | — | ✅ |
| Synchroniser les événements depuis HelloAsso | — | ✅ | — | ✅ |

Constantes : `_POLE_ADMIN_ROLES = ("Super Admin",)` (`poles.py:23`),
`_CATEGORY_ADMIN_ROLES = ("Super Admin",)` (`expense_categories.py:26`),
`_EVENT_ADMIN_ROLES = ("AdminBenevoles", "Super Admin")` (`events.py:24`).

### Endpoints

- `GET /poles?include_inactive=`, `POST|PATCH|DELETE /poles[/{id}]`.
- `GET /expense-categories?include_inactive=`,
  `POST|PATCH|DELETE /expense-categories[/{id}]`.
- `GET /events?include_inactive=&search=`, `POST /events/sync`,
  `POST|PATCH|DELETE /events[/{id}]`.

### Écrans

Sections de `/admin` : `PolesManagementSection` et
`ExpenseCategoriesManagementSection` (visibles si `ACTIONS.POLES_MANAGE`, soit
Super Admin), `EventsManagementSection` (si `ACTIONS.EVENTS_MANAGE`, soit
AdminBenevoles et Super Admin) — `AdminPage.tsx:104-108`.

### Règles métier

- **Un pôle `is_default` ou référencé par une facture ne se supprime pas**, il se
  désactive. Même règle pour une catégorie de dépense `is_default` ou déjà
  utilisée.
- **`GET /events` sert toujours le cache local** : une indisponibilité de
  HelloAsso ne doit jamais empêcher un bénévole de déposer une pièce
  (`events.py:34-38`).
- La famille d'événement (`type_ev`) se renseigne à la main ; HelloAsso ne la
  connaît pas (cf. §6).
- La lecture est ouverte à tout compte authentifié — les formulaires de dépôt en
  ont besoin.

---

## 12. Buvette (HelloAsso)

### Ce que ça permet

Suivre le stock des produits de la buvette et l'historique des ventes. Les
ventes arrivent en temps réel par un webhook HelloAsso, qui décrémente le stock.
Les produits se synchronisent depuis la boutique HelloAsso, ou se créent à la
main.

### Qui a le droit de quoi

| Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| Consulter produits et ventes | — | ✅ | ✅ | ✅ |
| Créer / modifier / supprimer un produit, ajuster stock, seuil, emoji | — | ✅ | — | ✅ |
| Synchroniser les produits depuis HelloAsso | — | ✅ | — | ✅ |
| Consulter le statut du webhook | — | ✅ | — | ✅ |
| Configurer / supprimer le webhook | — | — | — | ✅ |
| Rechercher un produit par code-barres | ✅ | ✅ | ✅ | ✅ |

`_VIEW_ROLES = ("AdminBenevoles", "Super Admin", "Compta")` (`buvette.py:45`) :
« la buvette est un outil de gestion, pas un écran de consultation ».
`GET /buvette/products/by-barcode/{barcode}` est en revanche ouvert à tout
compte authentifié (`buvette.py:97-107`) — asymétrie assumée ou non, elle est
signalée telle quelle.

### Endpoints

`GET /buvette/products`, `POST /buvette/products`,
`PATCH /buvette/products/{id}`, `DELETE /buvette/products/{id}`,
`GET /buvette/products/by-barcode/{barcode}`, `POST /buvette/sync`,
`GET /buvette/sales?limit=&offset=`, `GET /buvette/webhook/status`,
`POST /buvette/webhook/configure`, `DELETE /buvette/webhook`, et
`POST /buvette/webhook/helloasso` — **endpoint public**, appelé par HelloAsso.

### Écrans

`/buvette` (`BuvettePage.tsx`) et `/buvette/sales` (`BuvetteSalesPage.tsx`), avec
`CreateProductModal`, `AdjustStockModal`, `AddBuvetteFromBarcodeModal`,
`WebhookConfigModal`.

### Règles métier

- **Le webhook est public et idempotent** : la contrainte d'unicité
  (`helloasso_payment_id`, `helloasso_item_id`) empêche de compter deux fois la
  même vente lors d'un rejeu HelloAsso.
- **Le webhook répond toujours 200**, y compris sur secret invalide, JSON
  illisible ou schéma inattendu (`buvette.py:295-327`). Un 4xx renseignerait un
  attaquant sur l'existence du secret, et un 5xx déclencherait des tempêtes de
  réessais HelloAsso.
- **Sans `HELLOASSO_WEBHOOK_SECRET` configuré, l'endpoint laisse tout passer** —
  comportement historique conservé, mais journalisé en avertissement : un tiers
  peut alors forger des ventes (`buvette.py:266-279`).
- Le secret voyage **dans l'URL** enregistrée chez HelloAsso : c'est la seule
  forme d'authentification qu'accepte leur système de notifications
  (`buvette.py:335-342`).
- Une vente qui fait passer un produit sous son seuil déclenche une alerte, une
  seule fois : `alert_sent` est posé **avant** la tâche de fond, pour éviter les
  doublons (`buvette.py:239-252`).
- Événements traités : `Order` et `Payment` (via `data.order`). `Form` est
  ignoré.
- `GET /buvette/webhook/status` se replie sur l'activité des ventes quand
  HelloAsso refuse de relire sa propre configuration : les ventes déjà reçues
  sont la seule preuve directe que le webhook fonctionne (`buvette.py:366-379`).

### Écart constaté

Les routes `/buvette` et `/buvette/sales` **ne portent aucune garde côté
routeur** (`App.tsx:127-128`), alors que le menu les cache aux `Benevole` via
`ACTIONS.BUVETTE_VIEW`. Un bénévole qui saisit l'URL atteint le composant ;
seul le back refuse les données (403 sur `GET /buvette/products` et
`GET /buvette/sales`).

---

## 13. Scanner de documents et de codes-barres

### Ce que ça permet

Photographier un justificatif avec la caméra, laisser l'application détecter les
quatre coins du document, corriger le cadrage à la main, puis obtenir l'image
redressée — en PDF pour le dépôt, en JPEG pour l'aperçu. Séparément, scanner un
code-barres pour retrouver ou créer un article.

### Qui a le droit de quoi

`POST /scan/detect` et `POST /scan/apply` sont ouverts à **tout compte
authentifié** (`scan.py:66, 83`). Aucun filtre de rôle : le scanner sert à
déposer une pièce, ce que les quatre rôles peuvent faire.

Le scanner de codes-barres appelle `GET /stock/lookup-barcode/{barcode}`,
également ouvert à tout compte authentifié, mais les actions qui en découlent
(créer un article, créer un produit buvette) restent réservées à
`_ADMIN_ROLES`.

### Écrans

`DocumentScanner.tsx`, appelé depuis `MyExpensesPage.tsx` et
`InvoiceUploadPage.tsx` ; `BarcodeScanner.tsx` et `ScannedProductPreview.tsx`
depuis les écrans stock et buvette.

### Règles métier

- **Deux appels plutôt qu'un** : `detect` propose un cadrage que l'écran affiche
  en surimpression, `apply` produit le document. Ce découpage laisse le déposant
  corriger un cadrage erroné avant que le fichier ne parte au comptable.
- `corners` vaut `null` quand rien ne se détache : le scan s'applique alors sur
  la photo entière.
- **Le cadrage manuel exige exactement 4 points** `{x, y}` en pixels de la photo
  d'origine (`scan.py:105-109`).
- **Formats acceptés : JPEG et PNG uniquement**, et la limite
  `MAX_UPLOAD_MB` s'applique côté serveur — rien n'oblige un client à respecter
  la contrainte du navigateur (`scan.py:41-60`).
- Le résultat rejoint le **flux de dépôt existant** : conversion PDF et
  nomenclature comptable inchangées, pour qu'un fichier scanné suive exactement
  le même chemin qu'un fichier téléversé.

---

## 14. Notifications

### Ce que ça permet

Un seul appel renvoie tout ce qui attend l'utilisateur connecté. Il alimente les
pastilles du menu latéral et le rappel affiché une fois par connexion.

### Endpoint

`GET /notifications/summary` — tout compte authentifié.

### Écran

`Sidebar.tsx` (pastilles sur `/expenses`, `/invoices/upload`, `/invoices`,
`/admin`, `/contact`) et le hook `useRappelConnexion` appelé par `AppLayout`.

### Compteurs et filtrage par rôle

| Compteur | Qui le voit non nul |
|---|---|
| `notes_a_valider` | `Compta`, `Super Admin` |
| `factures_a_traiter` (« En attente » + « En cours de traitement ») | `Compta`, `Super Admin` |
| `tickets_ouverts` | `Compta`, `Super Admin` |
| `modifications_stock` | `AdminBenevoles`, `Super Admin` |
| `articles_en_alerte` | `AdminBenevoles`, `Super Admin` |
| `comptes_a_valider` | `Super Admin` |
| `conversations_a_traiter` | selon la portée : `Compta` (boîte compta), `Super Admin` (les deux) |
| `justificatifs_demandes` | **tous**, chacun pour soi |
| `notes_suivies` · `factures_suivies` · `conversations_non_lues` | **tous**, chacun pour soi |

### Règles métier

- **Chaque compteur est filtré par les droits du demandeur, côté serveur.** Un
  bénévole n'apprend pas combien de comptes attendent une validation : le
  compteur vaut 0, comme s'il n'y avait rien. **Un compteur à 0 ne distingue pas
  « rien à traiter » de « pas concerné », et c'est voulu**
  (`notifications.py:9-11`).
- Un endpoint plutôt que des comptages côté client : ces derniers auraient imposé
  de télécharger les listes complètes de notes et de factures à chaque
  chargement de page, pour n'en afficher qu'un nombre.
- `notes_suivies` exclut les notes archivées.

---

## 15. Administration : export / import de base

### Ce que ça permet

Diagnostiquer la base (moteur, tables, nombre de lignes), exporter les tables en
ZIP de CSV, réimporter des CSV.

### Qui a le droit de quoi

`GET /admin/database/status`, `POST /admin/database/export`,
`POST /admin/database/import`, `POST /admin/database/check` : **`Super Admin`
seul**.

### Écran

`/admin/database` (`DatabaseManagementPage.tsx`), gardé par
`<ProtectedRoute requiredAction={ACTIONS.ADMIN_DATABASE}>` (`App.tsx:138-145`).

### Règles métier

- **La table `Admins` est exclue de l'export** pour raison de sécurité
  (`admin.py:48`). Les tables exportées : `Stock`, `Categories`,
  `SousCategories`, `NotesDeFrais`, `FichiersNotesDeFrais`, `Factures`,
  `FichiersFactures`, `StockModifications`, `AdminInvitations`.
- **L'import exige `confirm=true`**, faute de quoi il est refusé
  (`admin.py:148-151`). Le front le passe systématiquement, la confirmation
  utilisateur étant portée par une case à cocher.
- L'import **ignore les lignes en erreur** et les journalise plutôt que d'échouer
  en bloc ; le message de retour donne le nombre de lignes insérées par table.
- Le diagnostic porte sur la base que **la session utilise réellement**, pas sur
  le moteur global, et l'URL renvoyée est amputée de ses identifiants
  (`admin.py:74-90`).
- `POST /admin/database/check` (simple `SELECT 1`) **n'a aucun appelant côté
  front**.

---

## 16. Tableau récapitulatif rôle × action

Vérifié contre le code. Les lignes marquées **(nouveau)** ne figurent pas dans
`CLAUDE.md` §5 ; les lignes marquées **(écart)** en diffèrent.

| Page / Action | Benevole | AdminBenevoles | Compta | Super Admin |
|---|:--:|:--:|:--:|:--:|
| **Dashboard** (vue + alertes) | ✅ | ✅ | ✅ | ✅ |
| Stock — consulter | ✅ | ✅ | ✅ | ✅ |
| Stock — demander une modification | ✅ | ✅ ¹ | ✅ ¹ | ✅ ¹ |
| Stock — voir les demandes des autres **(nouveau)** | — | ✅ | — | ✅ |
| Stock — modification directe | — | ✅ | — | ✅ |
| Stock — approuver / refuser les demandes | — | ✅ | — | ✅ |
| Stock — CRUD articles / catégories / sous-catégories | — | ✅ | — | ✅ |
| Stock — import CSV inventaire | — | ✅ | — | ✅ |
| Stock — scanner un code-barres **(nouveau)** | ✅ | ✅ | ✅ | ✅ |
| **Notes de frais** — soumettre | ✅ | ✅ | ✅ | ✅ |
| Notes de frais — éditer sa note « En attente » | ✅ | ✅ | ✅ | ✅ |
| Notes de frais — éditer toute note, tout statut **(écart)** | — | — | ✅ | ✅ |
| Notes de frais — valider / refuser / commenter | — | — | ✅ | ✅ |
| Notes de frais — archiver / restaurer | — | — | ✅ | ✅ |
| Notes de frais — supprimer définitivement | — | — | — | ✅ |
| Notes de frais — relancer l'envoi comptable **(nouveau, sans écran)** | — | — | ✅ | ✅ |
| Justificatifs — écarter / rétablir | — | — | ✅ | ✅ |
| Justificatifs — ajouter à une note existante | ✅ (la sienne, non remboursée) | ✅ (la sienne, non remboursée) | ✅ | ✅ |
| Notes de frais — voir l'IBAN du déposant | — | — | ✅ | ✅ |
| **Remboursements** — enregistrer un versement | — | — | ✅ | ✅ |
| Remboursements — fiches et totaux par bénévole **(nouveau)** | — | — | ✅ | ✅ |
| Remboursements — consulter les siens | ✅ | ✅ | ✅ (tous) | ✅ (tous) |
| Remboursements — télécharger le justificatif | ✅ (les siens) | ✅ (les siens) | ✅ | ✅ |
| **RIB** — déposer / supprimer le sien | ✅ | ✅ | ✅ | ✅ |
| RIB en document — télécharger celui d'un autre | — | — | ✅ | ✅ |
| **Tickets** — demander, modifier, relancer, clore | — | — | ✅ | ✅ |
| Tickets — voir ce qu'on me demande | ✅ | ✅ | ✅ | ✅ |
| **Contact** — ouvrir un fil, répondre au sien | ✅ | ✅ | ✅ | ✅ |
| Contact — boîte de l'équipe | — | — | ✅ (`compta`) | ✅ (les deux) |
| Contact — changer le statut d'un fil | — | — | ✅ (sa portée) | ✅ |
| Contact — réorienter un fil **(écart)** | — | — | ✅ (sa portée) | ✅ |
| **Factures** — déposer | ✅ | ✅ | ✅ | ✅ |
| Factures — changer le statut + motif | — | — | ✅ | ✅ |
| Factures — archiver | ✅ (les siennes, « En attente ») | ✅ (idem) | ✅ (toutes) | ✅ |
| Factures — **restaurer** **(écart)** | — | — | ✅ | ✅ |
| Factures — relancer l'envoi comptable | — | — | ✅ | ✅ |
| **Scanner de documents** (`/scan/detect`, `/scan/apply`) **(nouveau)** | ✅ | ✅ | ✅ | ✅ |
| **Notifications** — résumé filtré par droits **(nouveau)** | ✅ | ✅ | ✅ | ✅ |
| **Référentiels** — lire pôles / événements / catégories **(nouveau)** | ✅ | ✅ | ✅ | ✅ |
| Référentiels — CRUD pôles **(nouveau)** | — | — | — | ✅ |
| Référentiels — CRUD catégories de dépense **(nouveau)** | — | — | — | ✅ |
| Référentiels — CRUD événements + sync HelloAsso **(nouveau)** | — | ✅ | — | ✅ |
| **Admin** — hub `/admin` **(nouveau)** | — | ✅ | ✅ | ✅ |
| Admin — valider / rejeter les comptes `pending` | — | — | — | ✅ |
| Admin — gérer utilisateurs et rôles | — | — | — | ✅ |
| Admin — invitations par courriel | — | — | — | ✅ |
| Admin — annuaire en lecture seule **(nouveau)** | — | — | ✅ | ✅ |
| Admin — export / import BDD | — | — | — | ✅ |
| Admin — file d'envoi : consulter, état, relancer **(nouveau)** | — | — | ✅ | ✅ |
| **Buvette** — consulter stock & ventes | — | ✅ | ✅ | ✅ |
| Buvette — synchroniser les produits HelloAsso | — | ✅ | — | ✅ |
| Buvette — CRUD produits / ajuster stock | — | ✅ | — | ✅ |
| Buvette — statut du webhook **(nouveau)** | — | ✅ | — | ✅ |
| Buvette — configurer / supprimer le webhook | — | — | — | ✅ |
| Buvette — produit par code-barres **(nouveau)** | ✅ | ✅ | ✅ | ✅ |

¹ Ouvert côté serveur à tout compte authentifié (`stock.py:405-408`) ; le
bouton n'est proposé qu'au `Benevole` côté écran.

---

## 17. Récapitulatif des écarts constatés

| # | Écart | Où |
|---|---|---|
| 1 | Le front appelle `POST /stock/alert`, qui **n'existe pas**. La route est `POST /stock/low-stock/notify` et renvoie un `MessageOut`, pas `{ recipients, items }`. Le bouton d'envoi des alertes du dashboard part en 404. | `frontend/src/api/endpoints/stock.ts:153` vs `backend/app/api/v1/endpoints/stock.py:362` |
| 2 | `TicketsManagementSection` est rendu **sans garde de rôle** sur une page ouverte à tous : un bénévole voit la carte « Demandes de justificatif » et son bouton, pour des appels qui répondent 403. | `frontend/src/pages/invoices/InvoiceListPage.tsx:116` |
| 3 | `/buvette` et `/buvette/sales` n'ont **aucune garde de route** alors que `ACTIONS.BUVETTE_VIEW` les cache du menu aux bénévoles. Seul le back refuse. | `frontend/src/App.tsx:127-128` |
| 4 | `CLAUDE.md` §5 laisse croire que le bénévole **restaure** ses factures archivées. La restauration est réservée à `Compta` / `Super Admin`. | `backend/app/crud/invoice.py:198` |
| 5 | `CLAUDE.md` §5 limite l'édition d'une note à « ses propres notes "En attente" » : le code autorise en plus `Compta` / `Super Admin` à éditer **n'importe quelle note, à n'importe quel statut**. | `backend/app/crud/expense.py:228-233` |
| 6 | La docstring de `transferer` annonce « le Super Admin seul » ; le contrôle réel autorise aussi `Compta` sur un fil de sa portée. | `backend/app/crud/conversation.py:181-191` |
| 7 | `POST /expenses/{id}/resend-compta-email` existe côté API, **sans écran**. | `backend/app/api/v1/endpoints/expenses.py:262` |
| 8 | Endpoints sans écran : `POST /stock/low-stock/notify`, `POST /admin/database/check`, `POST /invitations/cleanup`, `GET /stock/items/by-barcode/{barcode}`, `PUT /stock/items/{id}/quantity`, `GET /expenses/{id}/files`, `GET /buvette/products/by-barcode/{barcode}`. | — |
| 9 | `CLAUDE.md` §6 ne liste pas : `POST /auth/forgot-password`, `POST /auth/reset-password`, `GET /auth/reset-password/validate`, `POST /auth/login/json`, `PUT /stock/items/{id}/quantity`, `POST /stock/low-stock/notify`, `GET /stock/lookup-barcode/{barcode}`, `GET /stock/items/by-barcode/{barcode}`, `GET /tickets/destinataires`, `POST /expenses/{id}/resend-compta-email`, `POST /invitations/cleanup`, `POST /admin/database/check`, `POST /scan/detect`, `POST /scan/apply`, `GET /buvette/products/by-barcode/{barcode}`. | `CLAUDE.md` §6 |
| 10 | `GET /buvette/products/by-barcode/{barcode}` est ouvert à **tout compte authentifié**, alors que `GET /buvette/products` est réservé à `_VIEW_ROLES`. | `backend/app/api/v1/endpoints/buvette.py:97-107` |
| 11 | La route catch-all `*` est **hors** du bloc protégé : `NotFoundPage` s'affiche sans authentification ni layout. | `frontend/src/App.tsx:151` |
| 12 | Sans `HELLOASSO_WEBHOOK_SECRET`, le webhook public accepte tout : un tiers peut forger des ventes. Le code le journalise mais laisse passer. | `backend/app/api/v1/endpoints/buvette.py:266-279` |
