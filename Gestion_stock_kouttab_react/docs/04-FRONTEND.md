# 04 — Architecture du frontend

Ce document décrit l'application React qui vit dans `frontend/`. Il complète
`CLAUDE.md` §8 (conventions de code) en expliquant **pourquoi** chaque règle
existe : la plupart d'entre elles ont été écrites après un incident, et les
commentaires du code en gardent la trace.

Il ne traite ni le backend, ni le modèle de données, ni le déploiement, ni la
stratégie de tests.

---

## 1. La pile

| Rôle | Outil | Où le voir |
|---|---|---|
| Vue | **React 18** + **TypeScript strict** (`strict: true`) | `package.json:35-37`, `tsconfig.json` |
| Build & dev | **Vite 5** | `vite.config.ts` |
| Styles | **Tailwind CSS** + primitives **shadcn/ui** (Radix) | `package.json:20-27`, `src/components/ui/` |
| Routage | **React Router v6** | `src/App.tsx:94-152` |
| Données serveur | **TanStack Query v5** | `src/App.tsx:70-81`, `src/api/endpoints/` |
| État global | **Zustand** — **authentification uniquement** | `src/stores/auth.ts` |
| Formulaires | **React Hook Form** + **Zod** (via `@hookform/resolvers`) | `src/lib/schemas/` |
| HTTP | **Axios**, une instance unique avec intercepteurs | `src/api/client.ts` |
| Divers | Recharts (tableaux de bord), `@zxing/*` (codes-barres), `date-fns`, `lucide-react` | `package.json:28-42` |

Deux réglages de `vite.config.ts` méritent d'être connus :

- l'alias `@` pointe sur `src/` (`vite.config.ts:21-25`) — tous les imports
  internes passent par lui, jamais par des `../../..` ;
- `MOBILE=1 npm run dev` sert le front en **HTTPS auto-signé** et relaie `/api`
  vers le backend (`vite.config.ts:17-35`). Ce n'est pas du confort : le scanner
  de justificatifs et le lecteur de codes-barres appellent `getUserMedia`, que
  les navigateurs réservent aux origines sécurisées — `localhost` en fait
  partie, `http://192.168.x.x` non. Le relais évite en prime le blocage
  « contenu mixte » et le CORS.

Les écrans d'authentification sont importés statiquement ; **tout le reste est
chargé à la demande** via l'adaptateur `lazyNamed` (`App.tsx:26-28`), écrit une
fois parce que les pages sont exportées nommément et que `React.lazy` attend un
export `default`. Le `<Suspense>` existait déjà mais ne servait à rien, tous les
imports étant statiques : l'application livrait un bundle unique d'environ
1,5 Mo, scanner et graphiques compris, que la plupart des utilisateurs
n'ouvrent jamais (`App.tsx:30-33`).

---

## 2. L'organisation des dossiers

```
frontend/src/
├── main.tsx                 # montage React
├── App.tsx                  # routes, QueryClient, ErrorBoundary, Toaster
├── api/
│   ├── client.ts            # instance axios + intercepteurs (JWT, refresh, FormData)
│   └── endpoints/           # UN module par domaine : hooks TanStack Query
├── pages/                   # un dossier par domaine fonctionnel
├── components/
│   ├── ui/                  # primitives shadcn/Radix, sans métier
│   ├── layout/              # AppLayout, Sidebar, TopBar, ProtectedRoute
│   ├── forms/               # champs composés et formulaires réutilisés
│   └── shared/              # briques d'affichage transverses
├── hooks/                   # comportements réutilisables (use*)
├── lib/                     # logique pure, testable sans React
│   ├── i18n/fr.ts           # tout le texte utilisateur
│   └── schemas/             # un schéma Zod par formulaire
├── stores/auth.ts           # le seul état global
├── types/                   # types partagés (réexportés depuis api.ts)
└── test/                    # setup Vitest, serveur msw
```

### `api/client.ts` et `api/endpoints/`

`client.ts` porte **l'unique** instance axios de l'application, et rien d'autre
que le transport : URL de base, jeton, rafraîchissement, en-têtes. Aucun appel
métier n'y figure.

`api/endpoints/` porte un module par domaine (`expenses.ts`, `invoices.ts`,
`contact.ts`, `stock.ts`, `buvette.ts`, `users.ts`, `tickets.ts`,
`reimbursements.ts`, `referentials.ts`, `notifications.ts`, `admin.ts`,
`auth.ts`, `invitations.ts`, `scan.ts`). Chaque module suit le même plan, que
`expenses.ts` illustre bien :

1. les **clés de cache** en un objet dérivé (`expenses.ts:11-16`) — jamais de
   littéral `['expenses']` semé dans les composants ;
2. les **fonctions de transport**, `async`, privées au module
   (`expenses.ts:18-121`) ;
3. les **hooks exportés**, `useQuery` / `useApiMutation`
   (`expenses.ts:128-207`), chaque mutation invalidant elle-même les clés
   qu'elle a rendues fausses (`expenses.ts:141`).

C'est cette dernière propriété qui fait la valeur du dossier : l'invalidation
du cache est déclarée à côté de l'écriture, pas dans l'écran qui la déclenche.
Un nouvel écran qui consomme `useValidateExpense` hérite du rafraîchissement
sans y penser.

### `pages/`

Un dossier par domaine (`auth/`, `dashboard/`, `stock/`, `expenses/`,
`invoices/`, `buvette/`, `contact/`, `admin/`), avec deux conventions
observées :

- les fenêtres modales d'un domaine vivent dans son sous-dossier `modals/`
  (`pages/expenses/modals/`, `pages/stock/modals/`, `pages/buvette/modals/`) ;
- une page trop grande se découpe en **sections** exportées, pas en fichier
  unique de 2 000 lignes : `pages/admin/AdminPage.tsx` agrège une douzaine de
  `*Section.tsx`, `pages/dashboard/DashboardPage.tsx` quatre `tabs/*`.

Une page orchestre : elle lit des hooks, choisit ce qu'elle affiche, déclenche
des mutations. Elle ne contient ni appel réseau nu, ni règle de calcul — ces
deux-là ont leurs dossiers.

### `components/ui | layout | forms | shared`

- **`ui/`** : les primitives shadcn/ui posées sur Radix (`button`, `dialog`,
  `select`, `tabs`, `toast`, `table`…). Aucune connaissance du métier, aucun
  import de `@/api` ni de `@/lib/auth`. On les modifie pour la charte, pas pour
  un écran.
- **`layout/`** : la coquille de l'application — `AppLayout`, `Sidebar`,
  `TopBar`, et `ProtectedRoute` qui garde les routes (§5).
- **`forms/`** : les champs composés partagés par plusieurs formulaires —
  `EventSelect`, `CategorySelect`, `FileUploader`, `AttachmentNamesPreview`,
  `PasswordStrengthMeter`, `ProfileForm`. Ce dossier existe parce que
  `ProfileForm` avait été recopié à l'identique dans deux écrans, et qu'un champ
  ajouté d'un côté manquait de l'autre (`ProfileForm.tsx:21-27`).
- **`shared/`** : les briques d'affichage transverses — `StatusBadge`,
  `RoleBadge`, `EmptyState`, `LoadingSpinner`, `ErrorAlert`, `ErrorBoundary`,
  `KpiCard`, `Logo`, `CategoryIcon`.

Deux dossiers métier échappent à ce découpage parce qu'ils portent un appareil
technique lourd et localisé : `components/scanner/` (caméra, ZXing) et
`components/buvette/`.

### `hooks/`

Les comportements réutilisables, et **la logique métier extraite des
composants** : `useApiMutation` (toast d'erreur automatique),
`useApiErrorToast`, `useToast`, `useAuth`, `useDownloadAttachment`,
`useRappelConnexion`. Règle de nommage : `use*`, `camelCase`.

### `lib/`

Tout ce qui est **pur et testable sans React** : `naming.ts`, `money.ts`,
`format.ts`, `errors.ts`, `constants.ts`, `utils.ts`, `barcode.ts`,
`camera.ts`, `chart-theme.ts`. C'est le dossier le mieux couvert par les tests,
précisément parce qu'il ne demande ni rendu ni serveur simulé.

Deux sous-dossiers :

- **`lib/i18n/fr.ts`** — tout le texte utilisateur, un objet unique par domaine
  (`fr.nav`, `fr.auth`, `fr.expenses`, `fr.contact`…).
- **`lib/schemas/`** — un schéma Zod par formulaire (`auth.ts`, `expense.ts`,
  `invoice.ts`, `contact.ts`, `stock.ts`, `buvette.ts`), avec le type de
  valeurs inféré et exporté à côté (`ExpenseFormValues`, `ContactFormValues`…).

### `stores/`

Un seul fichier, `auth.ts`, et c'est intentionnel (§3). Le store persiste
`user`, `accessToken` et `refreshToken` sous la clé `kouttab-auth`
(`stores/auth.ts:32-39`).

### `types/`

`types/api.ts` porte les formes échangées avec l'API ; `types/index.ts` se
contente de les réexporter (`export * from './api'`). Les énumérations
métier — rôles, statuts — ne sont pas ici mais dans `lib/constants.ts`, parce
qu'elles servent aussi de **valeurs** (listes déroulantes, tables de couleurs)
et pas seulement de types.

---

## 3. Les conventions qui sont des règles

Ces quatre-là ne sont pas des préférences de style. Chacune ferme un défaut
constaté.

### 3.1 Tout appel réseau est déclaré dans `api/endpoints/`

**Jamais de `useQuery` ni de `fetch` en ligne dans une page.**

La raison n'est pas la propreté : c'est le **cache**. Une clé de requête écrite
en ligne dans un composant n'est connue de personne d'autre, donc aucune
mutation ne saura l'invalider. L'écran affiche alors des données périmées
jusqu'au rechargement, et le symptôme (« le statut ne change pas ») ne désigne
jamais sa cause. Regrouper les clés (`expenses.ts:11-16`) et les invalidations
(`expenses.ts:141, 149, 157, 205`) dans le même module rend le lien vérifiable
d'un coup d'œil.

Corollaire utile : c'est là qu'on décide **combien** d'allers-retours coûte un
écran. `fetchAllExpenses` ramène toutes les notes, archives comprises, en un
seul appel (`expenses.ts:23-35`), parce que l'écran comptable groupe et compte
localement et que la base est distante — un aller-retour par changement de
filtre coûterait plus cher que les quelques lignes archivées rapatriées.

### 3.2 `mutation.mutate(vars, { onSuccess })`, jamais `await mutateAsync` dans un `try/catch`

`useApiMutation` (`hooks/useApiMutation.ts:27-54`) enveloppe `useMutation` et
branche l'affichage de l'erreur **avant** le `onError` de l'appelant
(`useApiMutation.ts:49-52`), en s'appuyant sur `useApiErrorToast`
(`hooks/useApiErrorToast.ts:21-31`), qui traduit le code d'erreur via le
catalogue de `lib/errors.ts` et l'affiche entre parenthèses pour le support.

Trois conséquences :

1. le `catch` n'aurait rien à faire — le message est déjà à l'écran ;
2. `mutate` **ne rejette jamais**, donc pas de « unhandled rejection » depuis un
   `onClick` ;
3. le succès se traite là où il a du sens, dans le `onSuccess` de l'appel
   (`ValidateExpensesPage.tsx:426-433`, `ContactPage.tsx:199-206`,
   `ConversationThread.tsx:67`).

`mutateAsync` reste réservé aux cas qui exploitent réellement le résultat dans
la foulée — la recherche par code-barres, appelée en `silentToast`. Le drapeau
`silentToast` sert aussi quand l'écran affiche l'erreur autrement, par exemple
la page de connexion et son `<ErrorAlert>` (`useApiMutation.ts:12-16`).

### 3.3 Tout texte utilisateur vit dans `lib/i18n/fr.ts`

Aucune chaîne visible n'est écrite en dur dans un composant : `fr.expenses.…`,
`fr.contact.…`, `fr.common.…`. L'objectif immédiat n'est pas la traduction — un
seul français est livré — mais la **cohérence du vocabulaire**. Les mêmes
notions reviennent sur cinq écrans (« Rembourser », « Écarter », « Archivée »,
« À traiter ») ; dispersées, elles finissent par diverger, et un utilisateur qui
lit deux mots pour une même action croit à deux actions.

Le fichier porte aussi les explications utiles au lecteur du code : `fr.app`
signale une mention transitoire, l'application s'étant appelée « Kouttâb
Stock » (`lib/i18n/fr.ts:10-12`).

Les messages d'erreur venus de l'API suivent un chemin parallèle et assumé :
`lib/errors.ts:16-96` réplique le catalogue de codes du backend
(`AUTH_1001`, `VAL_5006`…) avec une formulation adaptée à l'écran ; un code
inconnu retombe proprement sur le message brut de l'API, déjà en français
(`errors.ts:125-148`).

### 3.4 L'état global se limite à l'authentification

`stores/auth.ts` est le seul store Zustand, et il ne contient que l'utilisateur
et les deux jetons. **Tout le reste est du server state**, détenu par TanStack
Query.

C'est une règle de correction, pas d'esthétique : une donnée serveur recopiée
dans un store devient une seconde source de vérité, qu'il faut ensuite
resynchroniser à la main à chaque mutation — exactement le travail que fait
déjà l'invalidation de cache, mais sans filet. Le réglage global du client
(`App.tsx:70-81`) fixe le cadre : `staleTime` de 60 s, un seul réessai,
`refetchOnWindowFocus` désactivé, et **aucun réessai sur les mutations** — une
mutation rejouée toute seule, sur un dépôt de pièce comptable, créerait un
doublon.

---

## 4. Le client HTTP (`api/client.ts`)

Une seule instance axios, `baseURL` prise dans `VITE_API_URL`, délai de 30 s
(`client.ts:5-11`).

### 4.1 Intercepteur de requête : le jeton

Le jeton d'accès est lu **dans le store à chaque requête**, jamais capturé une
fois pour toutes (`client.ts:14-19`) : `useAuthStore.getState()` fonctionne hors
composant, et garantit qu'un jeton rafraîchi entre-temps est bien celui qui
part.

### 4.2 Intercepteur de requête : le retrait du `Content-Type` sur les `FormData`

```ts
if (config.data instanceof FormData) {
  delete (config.headers as Record<string, string>)['Content-Type'];
}
```
`client.ts:32-34`

Le défaut que cela corrige (`client.ts:21-31`) : l'instance pose
`Content-Type: application/json` comme en-tête par défaut (`client.ts:10`), ce
qui **écrase la détection d'axios**. Un envoi de fichier partait donc étiqueté
JSON, et surtout **sans sa frontière** (`boundary`) — or c'est elle, et elle
seule, qui dit au serveur où chaque partie du corps commence et finit. Le
serveur ne parvenait pas à découper le corps et rendait un `VAL_5001`
(« Données invalides. », `errors.ts:69`) en 422, qui ne désignait aucun champ et
n'expliquait rien.

Chaque appel multipart devait donc penser à rétablir l'en-tête à la main. Cinq
le faisaient ; le dépôt du RIB l'avait oublié. Traiter le cas une fois dans
l'intercepteur supprime la catégorie entière de bugs, au lieu d'en corriger une
occurrence.

Deux détails comptent :

- on **retire** l'en-tête au lieu d'écrire `multipart/form-data` : seul le
  navigateur connaît la frontière qu'il va employer, l'écrire à la main
  reproduirait le bug ;
- les en-têtes explicites laissés dans les modules d'endpoints — par exemple
  `headers: { 'Content-Type': 'multipart/form-data' }` dans
  `api/endpoints/expenses.ts:52-54` — sont désormais neutralisés par
  l'intercepteur, qui s'applique quelle qu'en soit l'origine.

### 4.3 Intercepteur de réponse : rafraîchissement sur 401, avec file d'attente

`client.ts:52-124`. Le déclenchement est conditionné (`client.ts:68-73`) : un
401, ou le code explicite `AUTH_1010`, sur une requête pas encore rejouée
(`_retry`) et qui **ne vise pas `/auth/login` ni `/auth/refresh`** — sans cette
exclusion, un mot de passe erroné déclencherait une tentative de
rafraîchissement, et un échec de rafraîchissement se rafraîchirait lui-même.

Le point délicat est la **concurrence**. Un écran lance volontiers trois ou
quatre requêtes en parallèle ; si le jeton vient d'expirer, elles reçoivent
toutes un 401 en même temps. Sans coordination, chacune appellerait
`/auth/refresh` de son côté : quatre rafraîchissements concurrents, et une
rotation de jeton qui invalide ceux que les autres viennent d'obtenir. D'où le
verrou `isRefreshing` et la file `queue` (`client.ts:44-50`) : la première
requête rafraîchit, les suivantes s'inscrivent dans la file
(`client.ts:81-92`) et sont rejouées avec le nouveau jeton une fois
`flushQueue` appelé (`client.ts:106`).

En cas d'échec du rafraîchissement (`client.ts:110-119`) : la file est vidée en
erreur, la session effacée, et le navigateur renvoyé sur `/login`. La
redirection est faite ici, hors de React, parce qu'aucun composant n'est en
position de la décider — l'échec peut survenir sur une requête de fond.

Enfin, chaque erreur est tracée en console **en développement seulement**
(`client.ts:61-66`), le bloc étant retiré du bundle de production par Vite.

---

## 5. Les permissions côté écran

`lib/auth.ts` porte la matrice, en trois pièces :

- **`ACTIONS`** (`lib/auth.ts:7-34`) : le catalogue des actions, sous forme de
  chaînes `domaine:action` (`expenses:validate`, `admin:database`,
  `conversations:handle`…). Le type `Action` en est dérivé, si bien qu'une
  action inexistante ne compile pas.
- **`PERMISSIONS`** (`lib/auth.ts:38-75`) : action → rôles autorisés. Chaque
  entrée sensible cite explicitement son homologue serveur, parce que la table
  n'a de valeur que si elle reste alignée : `_VIEW_ROLES` de
  `endpoints/buvette.py` (`lib/auth.ts:59`), `_POLE_ADMIN_ROLES` et
  `_EVENT_ADMIN_ROLES` (`lib/auth.ts:64-65`), `PORTEE` de
  `crud/conversation.py` (`lib/auth.ts:69-71`), le contrôle de
  `crud/expense.supprimer_definitivement` (`lib/auth.ts:72-74`).
- **`canAccess(role, action)`** (`lib/auth.ts:77-80`), plus
  `hasAnyRole` (`lib/auth.ts:82-85`) pour les rares cas exprimés en rôles.

Dans les composants, on ne lit pas `PERMISSIONS` : on passe par
`useAuth().can(action)` (`hooks/useAuth.ts:10`), qui applique `canAccess` au
rôle de l'utilisateur du store.

Trois usages, tous les mêmes :

```ts
const { can } = useAuth();
const peutValider = can(ACTIONS.EXPENSES_VALIDATE);   // MyExpensesPage.tsx:70-71
const gereDesFils = can(ACTIONS.CONVERSATIONS_HANDLE); // ContactPage.tsx:47
```

— un onglet qui n'apparaît pas (`MyExpensesPage.tsx:99-110`), une entrée de
menu masquée (`Sidebar.tsx:35-60`), une route qui redirige vers
`/dashboard` (`ProtectedRoute.tsx:26-32`).

### Ceci est du confort d'affichage. L'autorité reste le serveur.

`canAccess` ne protège rien. Elle évite de proposer un bouton qui échouerait, et
elle évite d'afficher un onglet vide — ce qui est déjà beaucoup pour la lisibilité
d'un écran. Mais le code est livré au navigateur, l'état est modifiable, et une
requête peut être forgée sans passer par l'interface.

La conséquence pratique, à ne jamais inverser : **une action n'est autorisée que
parce que le serveur la vérifie**. Ajouter une entrée dans `ACTIONS` sans la
dépendance de rôle correspondante côté FastAPI ne crée pas une permission, cela
crée un trou. Et une divergence entre les deux tables ne se voit pas : elle
produit soit un bouton qui échoue en 403 (bénin, agaçant), soit un bouton absent
pour quelqu'un qui y a droit (invisible, on ne remonte pas ce qu'on ne voit
pas). C'est pour cela que `lib/auth.ts` cite ses homologues serveur en
commentaire, ligne à ligne.

Le même raisonnement vaut pour les compteurs : `usePendingSummary` sert des
totaux **déjà filtrés par les droits côté serveur**, et la barre latérale ne les
recoupe pas — un rôle sans droit reçoit des zéros (`Sidebar.tsx:36-39`).

---

## 6. Le téléchargement de pièces (`hooks/useDownloadAttachment.ts`)

Les liens de téléchargement pointaient directement sur l'API,
`<a href={url} download>`. Cela ne peut pas fonctionner : **un navigateur ne
joint aucun en-tête `Authorization` à une navigation**. Le jeton vit dans le
store, pas dans un cookie ; une navigation ne le porte donc nulle part, et
chaque téléchargement revenait en `AUTH_1011` — « Token invalide »
(`useDownloadAttachment.ts:9-13`).

Le hook passe par l'instance axios (`useDownloadAttachment.ts:26`), ce qui
rétablit le jeton **et** fait bénéficier le téléchargement de l'intercepteur de
rafraîchissement : une pièce ouverte après une longue session ne casse plus. Le
blob obtenu est transformé en `objectURL`, confié à un `<a>` éphémère
(`useDownloadAttachment.ts:28-34`), et l'URL n'est révoquée qu'au bout de dix
secondes — Safari interrompt le téléchargement si on la libère dans la foulée
du clic (`useDownloadAttachment.ts:35-37`).

Le paramètre `filename` sert la pièce sous son **nom comptable** plutôt que sous
le nom d'origine du téléphone (`_p9.png`), illisible pour le comptable
(`useDownloadAttachment.ts:15-16`) ; c'est `lib/naming.ts` qui le compose (§7).
`fileId` alimente `downloadingId`, qui permet de désactiver le seul bouton
concerné pendant la récupération.

Le constructeur d'URL qui servait l'ancien `<a href>` a été **supprimé**, et son
absence documentée sur place pour que personne ne le réintroduise
(`api/endpoints/expenses.ts:123-126`).

---

## 7. Les modules jumeaux

Deux modules du front dupliquent volontairement un module du back. Ce n'est pas
une duplication à résorber : c'est une contrainte assumée, avec son garde-fou.

### 7.1 `lib/naming.ts` ↔ `backend/app/services/naming.py`

Ils composent le nom des pièces envoyées au service comptable, au format
`{Pôle}_{Événement}_{AAAA-MM-JJ}.pdf`. Le module translittère et nettoie chaque
composant (`naming.ts:48-85`) : remplacements explicites que NFKD ne décompose
pas (`œ`, `€`, apostrophes… `naming.ts:18-36`), suppression des diacritiques,
filtrage ASCII pour les alphabets non translittérables, réduction à
`[A-Za-z0-9-]`, troncature sur un tiret, et une protection contre les noms
réservés de Windows — un fichier nommé `CON.pdf` rend une archive
indécompressable (`naming.ts:38-46`). `deduplicateFilenames`
(`naming.ts:129-149`) suffixe `-2`, `-3` : les justificatifs d'un même dépôt
partagent pôle, événement et date, donc leur nom.

**Pourquoi le dupliquer ?** Le backend reste seul juge du nom réellement
produit. La copie sert à montrer au déposant, **avant** validation, le nom que
portera sa pièce (`MyExpensesPage.tsx:194-224`,
`components/forms/AttachmentNamesPreview.tsx`), et à réafficher côté comptable
la pièce sous le nom qu'il a reçu par courriel plutôt que sous le nom brut du
téléphone (`ValidateExpensesPage.tsx:374-388`). Un aperçu qui appellerait le
serveur à chaque frappe est hors de question ; un aperçu faux serait pire que
pas d'aperçu.

### 7.2 `lib/money.ts` ↔ `backend/app/core/money.py`

`expenseTotal` calcule le montant réellement dû au bénévole : montant, moins ce
qui a déjà été remboursé, moins la remise obtenue chez le fournisseur, **borné à
zéro** — un remboursement négatif s'afficherait comme une dette du bénévole
envers l'association (`money.ts:18-27`). S'y ajoutent les conversions
euros/centimes, où `Math.round` est indispensable : `19.99 * 100` vaut
`1998.9999999999998` en virgule flottante, et une troncature donnerait 1998
centimes (`money.ts:29-38`).

Ce module est né de la même douleur que les autres règles : ces calculs étaient
recopiés dans chaque composant qui en avait besoin, et une correction ne se
propageait pas (`money.ts:1-7`).

**Pourquoi le dupliquer ?** Le front affiche le montant à la comptabilité ; le
back le grave dans le justificatif remis au bénévole et dans
`Remboursements.montant_total`. Une divergence produirait un document qui
contredit l'écran l'ayant déclenché (`backend/app/core/money.py:1-15`). Le back
travaille en `Decimal` de bout en bout, jamais en `float`, parce que la colonne
est un `DECIMAL(10,2)`.

### 7.3 La table de cas partagée

C'est le garde-fou, et la seule raison pour laquelle cette duplication est
tenable : **les deux implémentations sont couvertes par la même table de cas**
(`naming.test.ts` / `backend/tests/unit/test_naming.py`, `money.test.ts` /
`backend/tests/unit/test_money.py`). Toute divergence casse un test — c'est
voulu, et c'est écrit en tête des deux modules (`naming.ts:1-11`).

Autrement dit, la cohérence n'est pas confiée à la vigilance de qui modifie le
code : elle est vérifiée. Modifier l'un des deux fichiers sans l'autre fait
échouer la suite, du côté qu'on n'a pas touché.

---

## 8. Les écrans structurants

### 8.1 `MyExpensesPage` — une seule entrée pour les notes de frais

L'application proposait deux entrées de menu pour un même sujet : déposer, et
valider. Or la comptabilité fait les deux — elle dépose ses propres notes et
valide celles des autres — et naviguer entre deux pages pour cela n'avait pas de
sens (`MyExpensesPage.tsx:59-68`).

La page est donc un jeu d'onglets (`MyExpensesPage.tsx:89-131`) : **Soumettre**,
**Mes demandes**, **Remboursements**, **Valider** (conditionnel), **Profil**.
Points notables :

- l'onglet « Valider » n'apparaît qu'à qui en a le droit
  (`MyExpensesPage.tsx:71, 99-110`), et porte la pastille des notes à traiter,
  reprise de l'entrée de menu disparue ;
- l'onglet initial se lit dans le **fragment d'URL**
  (`MyExpensesPage.tsx:73-75`), ce qui permet à l'ancienne adresse
  `/expenses/validate` de survivre par une redirection vers `/expenses#valider`
  (`App.tsx:116-122`) — des signets et des liens de courriels la visent encore ;
- l'onglet « Profil » réutilise `ProfileForm` (§8.5) ;
- le formulaire de dépôt adapte ses champs au **pôle** choisi
  (`MyExpensesPage.tsx:332-426`) : événement et date sous un pôle événementiel,
  catégorie et description ailleurs. Changer de pôle **réinitialise** les champs
  de rattachement (`MyExpensesPage.tsx:177-192`) : sans ce nettoyage, un
  événement saisi puis un basculement laissait la valeur dans le formulaire —
  invisible, mais envoyée, et refusée par l'API avec un message que rien à
  l'écran n'expliquait ;
- l'aperçu des noms de pièces (`MyExpensesPage.tsx:194-224`) retombe sur la date
  de dépense tant que le formulaire est incomplet, pour rester lisible pendant
  la saisie ;
- « Mes demandes » signale la nouveauté par **un point, pas un compteur** : ce
  qui compte est qu'il y ait du nouveau, pas combien de fois
  (`MyExpensesPage.tsx:518-526`). Il affiche le versement qui a soldé la note et
  son justificatif (`MyExpensesPage.tsx:551-583`) — sans quoi le bénévole ne
  pouvait ni dater ni prouver son remboursement depuis l'application — ainsi que
  les pièces écartées et de quoi les remplacer (`MyExpensesPage.tsx:585-589`).

### 8.2 `ValidateExpensesPage` — vues filtrées et groupement par bénévole

L'écran comptable est en **trois niveaux : bénévole → ses notes → le détail**
(`ValidateExpensesPage.tsx:95-104`). La raison est métier : la comptabilité ne
rembourse pas une note, elle rembourse **une personne** — un virement couvre
plusieurs dépenses. Une liste plate obligeait à reconstituer de tête ce que l'on
devait à chacun.

Le groupement est **local** (`ValidateExpensesPage.tsx:119-122`) :
`useAllExpenses` rapporte déjà toutes les notes avec le nom du déposant, et un
second appel serveur coûterait un aller-retour vers une base distante sans rien
apprendre. Les fiches sont triées avec en tête ceux qui attendent un versement —
le travail du jour (`ValidateExpensesPage.tsx:230-232`).

### Le principe des « vues »

`VUES` (`ValidateExpensesPage.tsx:65-85`) est un objet constant qui associe à
chaque vue un **libellé** et une **garde**, `(n: Expense) => boolean` :
`traiter`, `approuvees`, `remboursees`, `archivees`, `toutes`. La fonction
`visible(note, vue)` (`ValidateExpensesPage.tsx:89-93`) ajoute la seule règle
transverse : **les archives ne remontent que dans leur propre vue et dans
« Toutes »**.

Ce petit dispositif rend trois services que le filtrage serveur ne rendait pas :

1. **le compte de chaque vue est calculable d'un coup**
   (`ValidateExpensesPage.tsx:111-117`), et s'affiche sur chaque filtre — c'est
   ce qui dit d'un œil s'il reste du travail, sans avoir à y entrer ;
2. changer de filtre ne coûte **aucune requête** ;
3. la définition d'une vue tient sur une ligne, relisible et vérifiable.

L'écran s'ouvre sur `traiter`, sa raison d'être (`ValidateExpensesPage.tsx:109`).
Cette vue retient « En attente » **et** « Approuvée » : elle ne montrait que les
premières, si bien que le bouton « Rembourser » — qui n'apparaît qu'en présence
de notes approuvées — était invisible sur l'écran d'accueil, et qu'il fallait
deviner qu'il fallait changer de filtre pour pouvoir payer
(`ValidateExpensesPage.tsx:66-70`).

Le même patron a été repris pour les factures (§8.3).

### Pourquoi le total dû se calcule sur toutes les notes, et non sur celles affichées

`groupeParBenevole` sépare deux choses qu'on avait confondues
(`ValidateExpensesPage.tsx:195-233`) :

- ce qui est **affiché** dépend du filtre choisi :
  `notes: notesDuBenevole.filter((n) => visible(n, vue))`
  (`ValidateExpensesPage.tsx:222`) ;
- ce qui est **dû** n'en dépend pas :
  `aRembourser` retient toutes les notes « Approuvée » et non archivées, quel
  que soit le filtre, et `totalDu` en est la somme
  (`ValidateExpensesPage.tsx:216-224`).

Calculer le total sur les seules notes visibles faisait tomber « Reste à
rembourser » à zéro dès qu'on regardait un autre onglet, et retirait les cases à
cocher avec lui. **La somme due à quelqu'un ne change pas selon l'écran qu'on
consulte** : c'est un fait comptable, pas une propriété d'affichage. Les notes
archivées sont exclues du dû parce qu'elles sont sorties du circuit — les
proposer au paiement ferait payer deux fois ce que la comptabilité avait rangé
(`ValidateExpensesPage.tsx:214-218`).

La réciproque est vraie et tout aussi importante : **on ne coche que ce qui est
à l'écran** (`ValidateExpensesPage.tsx:248-255`). `aRembourser` porte tout ce qui
est dû — c'est ce que la pastille annonce — mais sélectionner une note que le
filtre courant masque reviendrait à payer à l'aveugle.

Le détail d'une note (`ValidateExpensesPage.tsx:367-691`) porte le reste : le
RIB et son document, les justificatifs sous leur nom comptable, l'écart et son
motif, le versement (`BlocVersement`, `ValidateExpensesPage.tsx:693-755`),
l'archivage, et la zone de suppression définitive réservée au Super Admin. Deux
règles d'affichage y méritent lecture : « Remboursée » est **retirée** de la
liste des statuts, parce qu'elle se constate et ne se déclare pas
(`ValidateExpensesPage.tsx:617-627`) ; et une note soldée par un versement
verrouille son statut, seul le commentaire restant modifiable
(`ValidateExpensesPage.tsx:400-402`).

### 8.3 `InvoiceListPage`

Même patron de vues, mêmes raisons (`InvoiceListPage.tsx:48-79`) :
`attente`, `encours`, `validees`, `refusees`, `archivees`, `toutes`, chacune avec
son compte (`InvoiceListPage.tsx:94-102`). Le menu déroulant précédent demandait
au serveur une liste par statut sans jamais dire combien il en restait ailleurs.

Le partage des responsabilités entre client et serveur y est explicite
(`InvoiceListPage.tsx:87-92`) : **la recherche et la date restent côté serveur**,
parce qu'elles portent sur le nom des pièces jointes, que le client n'a pas ;
**le statut se répartit localement**. C'est le bon critère — on filtre côté
client ce dont le client dispose déjà, pas plus.

La section des demandes de justificatif (`TicketsManagementSection`) est montée
en tête de cet écran (`InvoiceListPage.tsx:114-116`) : c'est en parcourant les
pièces reçues que la comptabilité constate ce qui manque.

### 8.4 `ContactPage` + `ConversationThread`

`ContactPage` (`ContactPage.tsx:32-42`) remplace un formulaire d'envoi par des
**fils de discussion**. Le formulaire précédent envoyait un courriel et n'en
gardait rien : la réponse partait de la boîte du comptable, hors de
l'application, et personne ne pouvait dire quelles questions restaient sans
réponse.

Trois onglets (`ContactPage.tsx:62-111`) : « Mes conversations », « Nouvelle
conversation », et « À traiter » réservé à qui gère les fils
(`ContactPage.tsx:47`). Les deux premiers portent une pastille alimentée par
`usePendingSummary`. Le formulaire d'ouverture ne comporte **aucun champ « votre
nom » ni « votre adresse »** : le serveur reprend l'identité du compte connecté
(`ContactPage.tsx:40-41`, mention affichée `ContactPage.tsx:263`) — un nom saisi
à la main se remplit de n'importe quoi.

L'ouverture d'un fil bascule sur l'onglet « Mes conversations » et l'affiche
directement (`ContactPage.tsx:93-100`) : la conversation qu'on vient de créer est
ce qu'on veut voir.

`ConversationThread` (`ConversationThread.tsx:32-38`) affiche le fil et de quoi
répondre. Trois choix explicites :

- **pas de temps réel** : le fil se recharge à chaque envoi. Une question de
  bénévole se traite dans la journée, pas à la seconde, et une connexion
  permanente coûterait un serveur de plus à surveiller ;
- le défilement va au **dernier message** à chaque nouveau message
  (`ConversationThread.tsx:56-60`) — sans cela un fil un peu long s'ouvre sur la
  question posée trois semaines plus tôt ;
- répondre reste possible sur un fil « traité » : côté serveur, cela le rouvre
  (`ConversationThread.tsx:140-141`). La bascule de statut n'est offerte qu'en
  mode `gestion`, c'est-à-dire à l'équipe (`ConversationThread.tsx:78-101`).

`StatutPuce` est exporté depuis ce fichier et réutilisé par la liste
(`ConversationThread.tsx:159-172`, `ContactPage.tsx:169`).

### 8.5 `ProfileForm`

Un composant partagé, et c'est tout son intérêt : le formulaire existait en
double, à l'identique, dans `ProfilePage` et dans l'onglet « Profil » de
`MyExpensesPage` — un champ ajouté d'un côté manquait de l'autre
(`ProfileForm.tsx:21-27`).

Il utilise `values` plutôt que `defaultValues` (`ProfileForm.tsx:33-44`), de
sorte que le formulaire se réaligne quand le profil arrive du serveur, sans
`reset` manuel.

Le dépôt du RIB en document est **hors du formulaire** (`ProfileForm.tsx:86-90`,
composant `RibDocument` `ProfileForm.tsx:96-184`) : il est immédiat et n'attend
pas « Mettre à jour ». Imbriquer un envoi de fichier dans la soumission du profil
obligerait à re-téléverser le RIB à chaque correction de numéro de téléphone.
Détail de mise en œuvre qui vaut d'être retenu : le champ `<input type="file">`
est réinitialisé dès la sélection (`ProfileForm.tsx:109-116`), faute de quoi
redéposer le **même** fichier après une suppression ne déclenche aucun événement
`change`.

---

## 9. Note sur `EventSelect` : un affichage ne doit jamais contredire ce qui sera soumis

`components/forms/EventSelect.tsx` est un sélecteur d'événement avec repli en
**saisie libre**. Ce repli est un cas normal, pas une panne : la liste vient
d'une synchronisation HelloAsso, et toutes les dépenses ne s'y rattachent pas —
une facture d'électricité n'a aucun événement (`EventSelect.tsx:35-42`).

### Le défaut corrigé

Le mode « saisie libre » était **déduit de la valeur saisie** :
`freeText ? FREE_EVENT : ''`. Choisir « Mon événement n'est pas dans la liste »
laissait le texte vide, la valeur du `<Select>` retombait donc à `''`, et le
champ de saisie **n'apparaissait jamais**. Il était impossible d'entrer le nom
d'un événement absent du référentiel, alors que le formulaire l'exigeait : le
dépôt était bloqué net (`EventSelect.tsx:54-63`).

Le correctif tient en une ligne : le mode est un **état à part**
(`EventSelect.tsx:64`), synchronisé avec ce que le formulaire impose —
réinitialisation après envoi, changement de pôle (`EventSelect.tsx:66-71`) — et
non déduit du contenu du champ. La sentinelle `FREE_EVENT`
(`EventSelect.tsx:13-14`) distingue explicitement « aucun choix » de « choix :
hors liste ».

### La règle générale

**Un affichage ne doit jamais contredire ce qui sera soumis.** Ce qui est montré
et ce qui partira doivent venir de la même source ; dès que l'un est *deviné* à
partir de l'autre, les deux finissent par diverger, et l'écart est silencieux —
personne ne voit ce que le formulaire contient réellement.

La même règle est citée mot pour mot ailleurs, sur un défaut symétrique
(`ValidateExpensesPage.tsx:410-419`) : l'écran de validation affichait
« Approuvée » tout en gardant « Remboursée » dans le formulaire ; cliquer sur
« Mettre à jour » sans toucher à la liste renvoyait le statut inchangé, le
serveur l'acceptait comme un non-changement, et le message « Statut mis à jour »
s'affichait alors que rien n'avait bougé. La correction consiste à faire ouvrir
le formulaire **sur la valeur qu'il va réellement envoyer**
(`ValidateExpensesPage.tsx:396-398, 420`).

Deux corollaires appliqués dans le même composant :

- ce que le contrôle propose doit correspondre à ce que le serveur acceptera —
  d'où la case décochée **et inerte** pour une note pas encore approuvée
  (`ValidateExpensesPage.tsx:318-327`), et le retrait de « Remboursée » de la
  liste des statuts (`ValidateExpensesPage.tsx:617-627`) ;
- et un statut hérité de la version Streamlit, écrit sans accents, doit être
  ramené à son écriture canonique avant d'alimenter un formulaire
  (`normaliserStatut`, `lib/constants.ts:10-36`), sans quoi le schéma Zod le
  rejette et « Mettre à jour » ne part jamais, **en silence** — encore un écart
  invisible entre l'écran et l'envoi.

Deux autres décisions d'`EventSelect` relèvent du même souci de ne pas mentir à
l'utilisateur : la saisie libre est proposée **en tête** de liste, où elle reste
visible même quand le référentiel compte des dizaines d'événements — en fin de
liste, les déposants concluaient que le leur ne pouvait pas être saisi
(`EventSelect.tsx:118-122`) ; et un référentiel indisponible bascule d'office en
saisie libre plutôt que de bloquer le dépôt (`EventSelect.tsx:73, 132-134`).

Enfin, le filtrage par famille d'événements est **volontairement permissif**
(`EventSelect.tsx:76-89`) : les événements de la famille demandée **et ceux qui
n'en ont aucune**. La famille se renseigne à la main — HelloAsso ne la connaît
pas — donc filtrer strictement viderait la liste au lendemain de chaque
synchronisation, chaque événement importé arrivant non classé.
