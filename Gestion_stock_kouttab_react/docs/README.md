# Documentation — Le Kouttâb, gestion

Application de gestion de l'institut associatif **Le Kouttâb** : inventaire,
notes de frais, factures, remboursements, buvette. Réécriture React + FastAPI
d'une application Streamlit historique, sur la même base MySQL.

Production : **https://stock.lekouttab.fr**

---

## Par où commencer

**Vous découvrez le projet** → lisez `01-ARCHITECTURE.md`, puis
`03-FONCTIONNALITES.md`. Une heure suffit à comprendre ce que fait
l'application et comment elle est bâtie.

**Vous allez modifier du code** → `08-PIEGES-ET-BONNES-PRATIQUES.md` d'abord.
Il ne décrit pas le code : il décrit les erreurs déjà commises sur ce projet et
ce qu'elles ont coûté. C'est le document qui fait gagner le plus de temps.

**Vous allez déployer** → `06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md`, et
`DEPLOIEMENT-VPS.md` à la racine pour la procédure détaillée.

**Vous allez toucher au schéma** → `02-MODELE-DE-DONNEES.md`, section
migrations. Le schéma est partagé avec une base de production réelle.

---

## Les documents

| Fichier | Ce qu'on y trouve |
|---|---|
| [`01-ARCHITECTURE.md`](01-ARCHITECTURE.md) | Les couches du backend, ce que chacune a le droit de faire, et les parcours importants tracés bout en bout |
| [`02-MODELE-DE-DONNEES.md`](02-MODELE-DE-DONNEES.md) | Toutes les tables, les colonnes qui portent une décision, la chronologie des migrations, les invariants |
| [`03-FONCTIONNALITES.md`](03-FONCTIONNALITES.md) | Le catalogue complet : ce que l'application sait faire, qui a le droit de le faire, et les règles métier qui ne se devinent pas |
| [`04-FRONTEND.md`](04-FRONTEND.md) | L'organisation du front, les conventions qui sont des règles, les écrans structurants |
| [`05-SECURITE.md`](05-SECURITE.md) | Authentification, autorisation, données sensibles, dépôts de fichiers, points de vigilance |
| [`06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md`](06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md) | Développement, tests, production : variables, Docker, chaîne de déploiement, sauvegarde, retour arrière |
| [`07-TESTS.md`](07-TESTS.md) | Comment lancer les tests, comment on les écrit ici, et ce qu'ils ne couvrent pas |
| [`08-PIEGES-ET-BONNES-PRATIQUES.md`](08-PIEGES-ET-BONNES-PRATIQUES.md) | Les incidents réels du projet et la règle qu'on en tire |

À la racine du dépôt, en complément :

- **`CLAUDE.md`** — guide de travail destiné aux assistants IA. Il recoupe cette
  documentation en plus condensé, et porte les conventions de contribution.
- **`DEPLOIEMENT-VPS.md`** — procédure d'exploitation du VPS, pas à pas.
- **`prd.md`** — intentions produit et feuille de route.

---

## En une page

**Ce que fait l'application.** Les bénévoles déposent leurs notes de frais et
les factures réglées avec la carte de l'association. La comptabilité valide,
demande des corrections, rembourse par virements groupés et reçoit chaque pièce
par courriel sous une nomenclature qui permet de l'imputer sans l'ouvrir. Le
stock et la buvette — synchronisée avec HelloAsso — se gèrent dans la même
application.

**Quatre rôles.** `Bénévole`, `AdminBenevoles`, `Compta`, `Super Admin`. La
matrice complète est dans `03-FONCTIONNALITES.md`.

**Trois principes** qui expliquent la plupart des choix du code :

1. **Ranger, pas détruire.** Une pièce comptable se conserve plusieurs années.
   L'archivage a remplacé les suppressions ; ce qui subsiste de destructeur est
   réservé au Super Admin, exige un motif, et le journalise.
2. **La base est la seule copie sauvegardée.** L'hébergeur sauvegarde la base,
   pas le disque du serveur. Tout document vit donc en base ; le disque n'est
   qu'un cache.
3. **Un affichage ne contredit jamais ce qui sera envoyé.** C'est la classe de
   bug la plus coûteuse rencontrée ici — trois incidents distincts, même cause.

**Pile technique.** FastAPI + SQLAlchemy 2 + Alembic côté serveur, React 18 +
TypeScript + TanStack Query côté navigateur, Docker Compose sur un VPS
mutualisé, base MySQL/MariaDB distante chez O2Switch, déploiement par GitHub
Actions.
