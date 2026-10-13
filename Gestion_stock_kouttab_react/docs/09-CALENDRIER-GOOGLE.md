# 09 — Calendrier Google

L'onglet **Calendrier** affiche, dans l'application, les agendas Google de
l'association : cours, réservations de salles, événements. En **lecture seule**.
Rien n'est recopié en base — Google reste la source de vérité, l'équipe continue
de saisir là où elle a l'habitude.

---

## 1. Ce qui a été écarté, et pourquoi

| Piste | Pourquoi non |
|---|---|
| **Iframe Google Agenda** | Seul un visiteur connecté à un compte Google ayant accès aux agendas verrait quelque chose. La plupart des bénévoles n'ont pas de compte `lekouttab.com` : ils auraient trouvé un cadre vide. |
| **Adresses iCal secrètes** | Une adresse par agenda, soit une quarantaine à recopier à la main — et une de plus à chaque rentrée, sans quoi le nouveau cours n'apparaît nulle part. |
| **Compte de service + délégation** | Retenu. Une configuration unique ; l'application voit ce que voit le compte impersonné, agendas futurs compris. |

Le connecteur Google d'un assistant IA n'est pas une option : il vit dans une
conversation, pas dans le serveur qui répond aux bénévoles.

---

## 2. Mise en service (une seule fois)

### 2.1 Créer le compte de service

1. [console.cloud.google.com](https://console.cloud.google.com) → créer (ou
   choisir) un projet, par exemple `kouttab-agenda`.
2. **APIs & Services → Library** → activer **Google Calendar API**.
3. **IAM & Admin → Service Accounts → Create service account**
   (nom : `kouttab-stock-calendrier`). Aucun rôle IAM n'est nécessaire : les
   droits viennent de la délégation, pas du projet.
4. Ouvrir le compte créé → onglet **Keys** → *Add key* → *Create new key* →
   **JSON**. Le fichier se télécharge **une seule fois** : il vaut mot de passe.
5. Sur ce même écran, relever le **Unique ID** (ou *Client ID*) — une longue
   suite de chiffres, demandée à l'étape suivante.

### 2.2 Accorder la délégation à l'échelle du domaine

Dans la console d'administration Workspace
([admin.google.com](https://admin.google.com), avec un compte administrateur du
domaine `lekouttab.com`) :

**Sécurité → Contrôle des données et des accès → Commandes des API →
Gérer la délégation au niveau du domaine → Ajouter**

- *Client ID* : le **Unique ID** relevé plus haut.
- *Champs d'application OAuth* :
  `https://www.googleapis.com/auth/calendar.readonly`

Un seul scope, en lecture. La délégation donne au serveur tout ce que voit le
compte impersonné : lui accorder l'écriture serait lui donner le droit de
supprimer des cours.

### 2.3 Renseigner le `.env` du serveur

```bash
# Encoder la clé en base64 — le JSON brut contient des sauts de ligne qui
# casseraient le fichier .env.
python -c "import base64,sys; print(base64.b64encode(open(sys.argv[1],'rb').read()).decode())" cle.json
```

```
GOOGLE_SERVICE_ACCOUNT_JSON=<la sortie ci-dessus>
GOOGLE_CALENDAR_SUBJECT=admin@lekouttab.com
GOOGLE_CALENDAR_RESTRICTED=
GOOGLE_CALENDAR_CACHE_SECONDS=180
```

`GOOGLE_CALENDAR_SUBJECT` **décide de tout ce que l'application voit** : les
agendas visibles sont exactement ceux de ce compte. Un agenda partagé plus tard
avec lui apparaît de lui-même ; un agenda qu'il perd disparaît.

Puis, sur le VPS : `docker compose up -d api` (le `.env` est relu au démarrage).
Le fichier JSON téléchargé n'a plus à exister nulle part — surtout pas dans le
dépôt.

### 2.4 Vérifier

Connecté en Super Admin : `GET /api/v1/calendar/etat` répond
`{"configure": true, "nombre_agendas": 42, ...}`.

| Symptôme | Cause habituelle |
|---|---|
| `configure: false` | Clé ou `GOOGLE_CALENDAR_SUBJECT` absent du `.env` |
| `EXT_6041` (`unauthorized_client` dans les journaux) | Délégation non accordée, ou scope différent au caractère près |
| `nombre_agendas: 0` | Le compte impersonné n'a lui-même aucun agenda |

---

## 3. Qui voit l'onglet

**AdminBenevoles, Compta et Super Admin** — pas les bénévoles. L'emploi du temps
porte les créneaux de chaque enseignant et les réservations de salles : c'est un
outil d'organisation, au même titre que la buvette.

La liste vit à deux endroits qui doivent rester jumeaux : `_ROLES_LECTURE` dans
`backend/app/api/v1/endpoints/calendar.py` et `ACTIONS.CALENDAR_VIEW` dans
`frontend/src/lib/auth.ts`. Le second ne fait que cacher une entrée de menu ;
c'est le premier qui refuse la requête.

## 4. Agendas réservés

`GOOGLE_CALENDAR_RESTRICTED` liste des identifiants d'agendas, séparés par des
virgules : ils ne sont servis qu'au **Super Admin**.

Prévu pour les rendez-vous de santé — un agenda « PSY RDV » porte des données
sensibles au sens du RGPD, et un titre d'événement suffit à nommer la personne
suivie. Le filtrage est fait **dans l'API** (`_agendas_visibles`), pas dans
l'interface : retirer une ligne d'un menu ne protège rien, l'appel HTTP reste à
la portée de tout compte connecté. Demander explicitement un agenda restreint
dans l'URL ne le rend pas non plus — un test le vérifie.

Vider la variable rouvre l'agenda à tout le monde ; c'est le seul geste à faire
quand un suivi se termine.

---

## 4 bis. Les salles, et pourquoi elles ne viennent pas de Google

L'onglet n'est pas un miroir de Google Agenda : c'est un **emploi du temps
d'école**. Trois colonnes de salle par journée — *Imam Maziri*, *Imam Nafi'*,
*Imam Zarrouq* — plus une colonne *Autre*.

### D'où vient la salle d'un cours

Trois sources, dans cet ordre, et **l'ordre n'est pas négociable** :

| Rang | Source | `salle_source` |
|---|---|---|
| 1 | Participant-ressource de l'événement (`attendees[].resource`) — la pièce est **réservée** dans Google Workspace | `google` |
| 2 | Le champ `location`, **seulement** s'il nomme une des trois salles | `google` |
| 3 | La salle **habituelle** de l'agenda, saisie dans l'application | `correspondance` |
| — | Rien de tout cela | `null` → colonne *Autre* |

**Pourquoi le rang 3 existe** : au relevé du 14 octobre 2026, seuls **22
événements sur 91 (24 %)** réservaient une salle. Sans correspondance, les
trois quarts de l'emploi du temps s'entasseraient dans *Autre*.

**Pourquoi `salle_source` est servi** : une salle de rang 3 est une *habitude*,
pas une réservation. La carte la signale par une bordure en pointillés. Les
présenter à l'identique enverrait un enseignant devant une porte occupée —
c'est la classe de bug décrite au §2 de `docs/08`.

Deux pièges de lecture, tous deux couverts par des tests :

- **`Zarruq` et `Zarrouq`** désignent la même pièce : Google écrit l'un,
  l'agenda du même nom écrit l'autre. La reconnaissance est faite sans accents,
  par sous-chaîne (`zarr`), jamais par égalité.
- **`location` est du texte libre.** « Salle 2 », « le kouttab » ou une adresse
  postale n'y donnent rien. Seule une **ressource** Google inconnue tombe dans
  *Autre* — là, quelqu'un a bel et bien bloqué une pièce.

### Les trois agendas « Salle - … » ne servent à rien

`Salle - Imam Maziri`, `Salle - Imam Nafi'`, `Salle - Imam Zarrouq` existent
chez Google et sont **vides** (0 événement). Ce ne sont pas les ressources :
les ressources sont des adresses `…@resource.calendar.google.com`, invisibles
dans la liste des agendas.

### Le libellé d'une carte

Le titre Google d'un cours est `cours 19` — illisible. Tout le sens est dans le
nom de l'agenda, `Coran - enfants 1 U.soundousse 2026/2027`. La carte affiche
donc :

```
Coran ENF 1        №19
U. Soundousse
              17:30–18:30
```

- **Le nom court** est calculé par `services/calendrier_salles.nom_court` :
  retrait de l'année scolaire et de l'enseignant, abréviations, puis retrait des
  mots de liaison *seulement si c'est encore trop long*, puis troncature à 22
  caractères. La règle tombe juste sur 44 des 45 agendas réels ; le dernier se
  corrige à la main.
- **L'enseignant** est lu dans le nom de l'agenda (`U.soundousse` → `U. Soundousse`).
  Tous les agendas n'en portent pas.
- **Le numéro de séance** vient de `extendedProperties.private.numero`, posé par
  l'outil qui génère les cours ; le titre `cours NN` n'est qu'un repli. Les
  permanences n'ont pas de numéro, et la carte l'omet.

La règle vit **en Python seul**. C'est délibéré : la calculer aussi côté front
créerait une troisième paire de modules jumeaux, après `naming` et `money`.

### L'écran de réglage

*Administration → Salles de l'emploi du temps*, **Super Admin seul**
(`_REGLAGES` dans `endpoints/calendar.py`, jumelé à `ACTIONS.CALENDAR_ROOMS_MANAGE`).
Ranger les agendas décide de ce que tout le monde lit.

- `GET|PUT /calendar/reglages-agendas` — **en lot**, et ce qui n'est pas envoyé
  n'est pas touché : l'écran règle dix agendas sur quarante-cinq et enregistre.
  `null` efface et rend le champ à son calcul.
- `GET /calendar/reglages-agendas/deduire?jours=60` — **propose** une salle par
  agenda d'après les réservations réellement trouvées. Rien n'est enregistré :
  la proposition remplit le formulaire, une personne valide.
- `GET /calendar/etat` compte les `agendas_sans_salle` — sans ce signal, une
  grille qui entasse tout dans *Autre* paraît cassée sans raison visible.

Table `CalendrierAgendaReglages` (migration `d1e7f2a4b6c8`) : `agenda_id`
unique mais **pas clé primaire** — un `String(255)` en utf8mb4 pèse 1020 octets
d'index, au-delà des 767 qu'autorise InnoDB en format `COMPACT`. C'est la seule
chose que l'application stocke du calendrier, et elle ne duplique rien de
Google : elle porte ce que Google n'a pas.

### Le pont SSO transporte aussi les réglages

`POST /auth/sso/calendrier` charge la même correspondance. L'oublier aurait
donné `salle: null` côté gestion pour les événements que l'onglet d'ici place
dans une colonne — deux chemins de lecture répondant différemment à la même
question, ce que le docstring de `services/calendrier.py` interdit.

---

## 5. Ce que l'application fait des données

- **Aucun stockage.** Ni table, ni migration. Un cache mémoire de quelques
  minutes (`GOOGLE_CALENDAR_CACHE_SECONDS`) évite 42 appels à Google à chaque
  changement de mois. Le bouton **Rafraîchir** le vide, pour voir tout de suite
  un horaire qu'on vient de corriger dans Google.
- **Les récurrences sont développées par Google** (`singleEvents`) : un cours
  hebdomadaire arrive comme autant d'occurrences datées, sans règle à
  interpréter.
- **Un agenda en panne ne vide pas la page** : les autres sont servis, et son
  nom est affiché en avertissement.
- **La fenêtre est plafonnée à 400 jours** par appel : au-delà, ce sont
  42 agendas multipliés par autant de mois, et les quotas Google se comptent à
  la requête.

## 6. L'aperçu figé — inerte depuis le 13 octobre 2026

> **Plus personne ne le lit.** La clé du compte de service est posée en
> production depuis le 2026-10-13 : `sur_instantane()` rend `false`, Google
> parle. Le relevé s'arrêtait de toute façon au 18 octobre.
>
> **Reste à faire** : supprimer `app/ressources/calendrier_instantane.json`,
> `services/calendrier_instantane.py`, le test dédié, les champs `instantane`
> et `genere_le` des schémas, et la bannière de l'écran. Ce ménage touche le
> contrat que lit `gestion.lekouttab.fr` — il mérite sa propre PR, pas un
> passager clandestin dans une refonte d'écran.

L'onglet est parti en production avant le compte de service. Plutôt qu'un écran
vide, il servait un **relevé daté** des agendas, pris le 2026-09-20 sur quatre
semaines (20 septembre → 18 octobre 2026, 195 événements, 41 agendas) :
`backend/app/ressources/calendrier_instantane.json`.

- **Google l'emporte toujours.** Dès que la clé et le compte impersonné sont
  posés, le relevé n'est plus lu — sans quoi il masquerait la source vivante et
  se tairait à chaque horaire corrigé. Le fichier peut alors être supprimé,
  avec `app/services/calendrier_instantane.py`.
- **L'écran le dit.** Une bannière donne la date du relevé et annonce que rien
  n'y bouge. Un planning daté qui se présenterait comme le direct ferait manquer
  un cours déplacé. Le bouton « Rafraîchir » disparaît : il ne promet rien.
- **« PSY RDV » n'y est pas.** Un fichier versionné reste dans l'historique Git
  pour de bon, et ces titres nomment les familles suivies. Cet agenda ne
  reviendra que par la connexion en direct, où le filtrage par rôle s'applique.
  Les descriptions et les participants sont également absents du relevé.
- **Les couleurs sont posées par famille de cours** : cet accès ne les expose
  pas. Les vraies arrivent avec le direct.
- **Le fichier ne vit pas dans `app/data/`** : `.gitignore` exclut tout dossier
  nommé `data/`, et le relevé aurait été absent de l'image construite par la CI
  sans que rien ne le signale.

Le relevé a été produit avec le connecteur Google Agenda d'un assistant, une
fois — il n'existe pas de script rejouable, et il n'en faut pas : l'étape 2
rend l'exercice inutile.

## 7. L'outil de gestion lit le même calendrier

`gestion.lekouttab.fr` affiche le même onglet, **sans second compte de service** :
son serveur signe un jeton court (`typ: 'sso-calendrier'`, 60 s, secret partagé
`SSO_SHARED_SECRET`) et appelle `POST /api/v1/auth/sso/calendrier`. Troisième
point d'une famille déjà en place — la pastille et les dépenses passent par le
même mécanisme.

Ce qui vaut d'être retenu :

- **Une seule connexion Google à configurer**, un seul cache, un seul endroit à
  corriger le jour où l'API bouge.
- **La fenêtre demandée est dans le jeton signé**, pas dans le corps : rien à
  substituer pour balayer l'année, même pour qui tiendrait le secret.
- **Les agendas réservés ne traversent jamais la frontière**, quel que soit le
  demandeur. Ils restent consultables ici, par un Super Admin.
- **Le droit d'ouvrir l'onglet est vérifié côté gestion**, où vivent ses rôles —
  ici on vérifie seulement que la question vient bien de l'outil de gestion.
  Même doctrine que `/sso/depenses`.

## 8. Fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/services/google_calendar.py` | Jeton JWT-bearer, appels Calendar v3, cache |
| `backend/app/services/calendrier.py` | Source, fenêtre, normalisation — partagé par l'onglet et le pont SSO |
| `backend/app/services/calendrier_salles.py` | Salle, enseignant, numéro de séance, nom court — **fonctions pures** |
| `backend/app/crud/calendrier.py` | La table de correspondance (la seule chose stockée en base) |
| `frontend/src/pages/admin/CalendrierSallesSection.tsx` | L'écran de réglage (Super Admin) |
| `backend/app/services/calendrier_instantane.py` | Le relevé figé (provisoire, cf. §5) |
| `backend/app/ressources/calendrier_instantane.json` | Le relevé lui-même |
| `backend/app/api/v1/endpoints/calendar.py` | `/calendar`, `/calendar/agendas`, `/calendar/etat`, `/calendar/rafraichir` |
| `backend/tests/integration/test_api_calendar.py` | Filtrage par rôle, normalisation, panne partielle |
| `frontend/src/pages/calendar/CalendarPage.tsx` | L'écran (FullCalendar : mois, semaine, jour, liste) |
| `frontend/src/api/endpoints/calendar.ts` | Hooks TanStack Query |

Le navigateur ne parle jamais à Google : il interroge l'API, qui seule détient
la clé. Aucun compte Google n'est donc nécessaire côté bénévole.
