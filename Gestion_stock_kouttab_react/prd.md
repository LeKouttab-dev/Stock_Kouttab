# Product Requirements Document — Kouttab Stock React

**Version** : 1.0
**Date** : 2026-05-04
**Auteur** : équipe technique
**Statut** : Draft (à valider avec le client Le Kouttâb)

---

## 1. Executive Summary

### Problem Statement
L'institut associatif **Le Kouttâb** utilise aujourd'hui une application Streamlit pour gérer son stock, ses notes de frais et ses factures. Cette application souffre de limitations UX (chargement complet à chaque interaction, navigation linéaire, pas de mobile responsive), d'une architecture monolithique tightly-coupled à Streamlit qui rend toute évolution coûteuse, et de risques de sécurité (sessions volatiles, hash SHA256, code métier mélangé à l'UI).

### Proposed Solution
Réécrire l'application en stack moderne **React + FastAPI** en **conservant la base de données MySQL O2Switch existante** (zéro perte de données). L'architecture sépare clairement frontend SPA, backend API REST et persistance, avec authentification JWT, stockage sécurisé des fichiers et workflow d'approbation préservés.

### Success Criteria
| KPI | Cible | Mesure |
|---|---|---|
| **Temps de chargement initial (first paint)** | < 1.5 s sur connexion 4G | Lighthouse |
| **Temps de réponse médian API** | < 200 ms sur endpoints CRUD | Logs FastAPI / Sentry |
| **Disponibilité** | ≥ 99.5 % / mois | Uptime-Robot sur `/api/v1/health` |
| **Adoption** | 100 % des utilisateurs actifs migrés en ≤ 4 semaines après le go-live | Comparaison sessions Streamlit vs nouvelle app |
| **Score Lighthouse Accessibilité** | ≥ 95 | Audit automatisé en CI |
| **Zéro perte de données** | 0 ticket de support sur "donnée manquante" lors de la bascule | Support post-deploy |

---

## 2. User Experience & Functionality

### 2.1 User Personas

#### Persona 1 : **Yasmine — Bénévole**
- **Profil** : 26 ans, étudiante, bénévole occasionnelle. Utilise l'app depuis son smartphone, ~2 fois/semaine.
- **Goals** : déclarer rapidement les courses qu'elle fait pour l'association ; consulter les stocks pour savoir ce qui manque.
- **Pain Points actuels** : interface Streamlit non mobile-friendly ; pas de notification quand sa note de frais est validée.
- **User Journey** : login → soumet une note de frais avec photo de ticket → consulte le statut quelques jours après.

#### Persona 2 : **Karim — AdminBénévoles**
- **Profil** : 42 ans, responsable logistique de l'association. Connecté tous les jours sur desktop.
- **Goals** : tenir l'inventaire à jour, valider les demandes de modification de stock, importer un inventaire en lot via CSV.
- **Pain Points** : modifications de stock parfois oubliées ; difficile de voir les alertes en un coup d'œil.
- **User Journey** : reçoit alerte email "stock bas" → connecté → consulte dashboard → approuve les demandes en attente → ajoute de nouveaux articles.

#### Persona 3 : **Sophie — Comptable**
- **Profil** : 38 ans, comptable bénévole, à distance. Utilise un PC professionnel.
- **Goals** : valider les notes de frais et factures, déclencher les remboursements, conserver une trace des justificatifs.
- **Pain Points** : besoin de copier le RIB du bénévole dans l'outil de virement bancaire ; doit télécharger les tickets un par un.
- **User Journey** : ouvre dashboard frais → expander note → vérifie justificatifs → copie RIB → fait le virement externe → met le statut à "Remboursée".

#### Persona 4 : **Hicham — Super Admin / Trésorier**
- **Profil** : 50 ans, président/trésorier. Délègue mais supervise.
- **Goals** : créer/désactiver des comptes, inviter de nouveaux admins par email, exporter la BDD pour archivage trimestriel.
- **Pain Points** : process de création de compte peu sécurisé (mots de passe partagés en clair par email).
- **User Journey** : invite un nouveau compta par email → reçoit notif validation → approuve → délègue ; tous les 3 mois exporte la BDD en ZIP.

### 2.2 User Stories & Acceptance Criteria

#### Authentification

**US-AUTH-1** — *En tant que visiteur, je veux me connecter avec mon username et mot de passe pour accéder à l'application.*
- AC : formulaire avec validation côté client (username 3-20 chars).
- AC : 5 échecs successifs → lockout 15 min affichant un message clair.
- AC : succès → redirige vers dashboard correspondant à mon rôle.
- AC : token JWT stocké, refresh automatique avant expiration.

**US-AUTH-2** — *En tant que visiteur, je veux créer un compte bénévole pour pouvoir soumettre mes notes de frais.*
- AC : formulaire complet (username, password, confirmation, rôle au choix `Benevole|AdminBenevoles|Compta`, nom, prénom, email, téléphone optionnel).
- AC : indicateur de force du mot de passe en temps réel (8+, maj, min, chiffre, symbole).
- AC : compte créé avec `validation_status='pending'` et message "en attente de validation".
- AC : email envoyé au Super Admin pour notifier.

**US-AUTH-3** — *En tant que Super Admin invité par email, je veux finaliser mon compte via un lien sécurisé.*
- AC : lien d'invitation valide 24 h, max 3 tentatives.
- AC : page de setup affiche email pré-rempli, demande username + password (8+ règles).
- AC : succès → compte créé `Super Admin`, `active`, login automatique.

#### Stock

**US-STOCK-1** — *En tant qu'utilisateur, je veux naviguer dans le stock par catégories puis sous-catégories pour trouver un article rapidement.*
- AC : page d'accueil stock affiche les catégories en grille avec icône + compteur articles + nombre d'alertes.
- AC : clic catégorie → liste des sous-catégories (ou directement articles si pas de sous-cat).
- AC : clic sous-catégorie → liste articles avec emoji, nom, quantité, seuil, badge "alerte" si applicable.
- AC : breadcrumb permet de revenir en arrière.

**US-STOCK-2** — *En tant que Bénévole, je veux demander une modification de quantité d'un article.*
- AC : bouton "Demander une modification" ouvre une modale.
- AC : champ quantité actuelle (lecture seule) + quantité souhaitée (number ≥ 0).
- AC : soumission crée une `StockModification` en attente.
- AC : toast confirmation.

**US-STOCK-3** — *En tant qu'AdminBénévoles, je veux modifier directement la quantité d'un article.*
- AC : bouton "Modifier" sur chaque article.
- AC : modale avec quantité actuelle + nouvelle quantité.
- AC : update immédiate, log dans `StockModifications` (status `Approuvée`, `approuve_par` = moi).
- AC : si nouvelle quantité < seuil ET `alert_sent=false` → email envoyé aux AdminBenevoles + Super Admin et flag passe à true.
- AC : si nouvelle quantité ≥ seuil ET `alert_sent=true` → flag remis à false.

**US-STOCK-4** — *En tant qu'AdminBénévoles, je veux importer un inventaire complet via CSV.*
- AC : page d'upload CSV avec aperçu (10 premières lignes).
- AC : colonnes attendues : Catégorie, Sous-catégorie, Nom de l'article, Quantité initiale.
- AC : `skiprows` paramétrable (défaut 6, héritage du legacy).
- AC : validation par ligne, articles existants ignorés, sous-catégories créées si manquantes.
- AC : compte-rendu : importés / ignorés / erreurs (top 10 affichées).

**US-STOCK-5** — *En tant qu'AdminBénévoles, je veux gérer le référentiel catégories et sous-catégories (CRUD).*
- AC : interface deux onglets (catégories / sous-catégories).
- AC : ajout, renommage, suppression. Suppression bloquée si articles existants (message clair).

**US-STOCK-6** — *En tant qu'AdminBénévoles, je veux approuver/refuser les demandes de modification en attente.*
- AC : page "Demandes en attente" liste les `StockModifications` avec status `En attente`.
- AC : bouton Approuver → met à jour Stock + status `Approuvée` + `approuve_par` + `date_approbation`.
- AC : bouton Refuser → status `Refusée` (sans toucher au stock).

#### Notes de frais

**US-EXPENSE-1** — *En tant que Bénévole, je veux soumettre une note de frais avec justificatifs.*
- AC : formulaire avec champs obligatoires (date, rattachement, montant) et optionnels (fournisseur, nature, commentaires, remboursement déjà émis, remise).
- AC : upload multi-fichiers (`png/jpg/jpeg`), max 10 Mo/fichier, max 5 fichiers.
- AC : soumission → email automatique aux Compta + Super Admin.
- AC : note visible dans "Mes demandes" avec statut `En attente`.

**US-EXPENSE-2** — *En tant que Bénévole, je veux éditer ou supprimer une note "En attente".*
- AC : bouton Éditer disponible uniquement si `status == "En attente"` ET propriétaire.
- AC : édition de tous les champs, ajout/suppression de fichiers.
- AC : pas de bouton Supprimer côté Bénévole (seul Compta peut supprimer une note `Remboursée`).

**US-EXPENSE-3** — *En tant que Comptable, je veux valider/refuser les notes de frais et tracer mes commentaires.*
- AC : dashboard liste toutes les notes avec expander par note.
- AC : affichage du RIB du bénévole avec bouton "Copier" (copie en clipboard, toast confirmation).
- AC : sélection statut (`En attente|Approuvée|Refusée|Remboursée`) + commentaire compta.
- AC : enregistrement notifie le bénévole (email).
- AC : statut `Remboursée` débloque le bouton "Supprimer définitivement" dans une zone dédiée.

**US-EXPENSE-4** — *En tant que Bénévole, je veux gérer mon profil (RIB notamment).*
- AC : page Profil avec champs nom, prénom, email, téléphone, IBAN/RIB.
- AC : RIB enregistré chiffré au repos en prod (AES-256, hors scope MVP — voir Roadmap).

#### Factures

**US-INVOICE-1** — *En tant qu'utilisateur, je veux déposer une ou plusieurs factures avec commentaire.*
- AC : upload multi-fichiers (`pdf/png/jpg/jpeg`), max 10 Mo/fichier.
- AC : note d'avertissement : "Facture au nom de Le Kouttâb ou E.C.L.A.T uniquement".
- AC : commentaire facultatif.
- AC : soumission → email au service compta.

**US-INVOICE-2** — *En tant qu'utilisateur, je veux visualiser les factures déposées avec filtres.*
- AC : filtres statut, date de dépôt, recherche par nom de fichier.
- AC : KPIs en haut (total / en attente / en cours / validées).
- AC : expander par facture avec déposant, date, fichiers téléchargeables.

**US-INVOICE-3** — *En tant que Compta, je veux changer le statut d'une facture.*
- AC : selectbox + bouton "Mettre à jour".
- AC : statuts disponibles : `En attente|En cours de traitement|Validée|Refusée`.

#### Dashboard

**US-DASH-1** — *En tant qu'utilisateur, je veux voir l'état du stock en un coup d'œil.*
- AC : 4 KPI cards (Total articles / Total quantité / Articles en alerte / Stock épuisé).
- AC : 2 graphes barres (articles par catégorie / sous-catégorie Nourriture).
- AC : tableau "Dernières activités" (5 dernières modifs).

**US-DASH-2** — *En tant qu'utilisateur, je veux consulter l'historique des modifications avec filtres.*
- AC : filtres période (1/7/30/90 j) + statut.
- AC : tableau triable + pagination.
- AC : 3 métriques (en attente / approuvées / refusées).

**US-DASH-3** — *En tant qu'utilisateur, je veux voir les articles en alerte et déclencher une notification email.*
- AC : tableau articles en alerte avec criticité (`🔴 Critique` qty=0, `🟡 Bas` sinon).
- AC : bouton "Envoyer email d'alerte" → SMTP aux AdminBenevoles + Super Admin.

#### Administration

**US-ADMIN-1** — *En tant que Super Admin, je veux valider/refuser les comptes en attente.*
- AC : liste des comptes pending avec username + rôle demandé.
- AC : Approuver → `validation_status='active'` ; Refuser → `delete_admin`.
- AC : email automatique au demandeur.

**US-ADMIN-2** — *En tant que Super Admin, je veux gérer les utilisateurs (changer rôle, supprimer).*
- AC : tableau de tous les comptes (sauf moi-même).
- AC : changement de rôle via selectbox + bouton.
- AC : suppression avec confirmation modale.

**US-ADMIN-3** — *En tant que Super Admin, je veux inviter un nouvel admin par email.*
- AC : formulaire avec email cible.
- AC : génération token + envoi email avec lien `https://stock.lekouttab.fr/admin-setup?token=...&email=...`.
- AC : invitation listée avec statut (utilisé/expiré/actif), bouton révocation.

#### Buvette (HelloAsso)

**US-BUVETTE-1** — *En tant qu'AdminBénévoles, je veux importer en un clic tous les produits de notre boutique HelloAsso "Buvette".*
- AC : bouton "Synchroniser depuis HelloAsso" sur la page Buvette.
- AC : appel à l'API HelloAsso `/v5/organizations/{slug}/forms/Shop/buvette/public` pour récupérer la liste des `tiers`.
- AC : upsert par `helloasso_tier_id` ; les nouveaux produits sont créés avec `quantity=0`, `seuil_alerte=5`, emoji `🥤` ; les existants voient leur `name`, `description`, `price_cents` mis à jour.
- AC : le stock local (`quantity`) n'est **jamais écrasé** par la sync.
- AC : compte-rendu après sync : `{créés, mis à jour, ignorés, erreurs}`.

**US-BUVETTE-2** — *En tant que membre du personnel, je veux voir l'état du stock de la buvette en temps réel.*
- AC : page `/buvette` accessible à tous les rôles authentifiés.
- AC : grille de cartes produits avec photo (image_url HelloAsso), nom, prix, quantité, badge couleur (rouge=rupture / jaune=bas / vert=OK).
- AC : badge "🔗 HelloAsso" si le produit est lié à un tier HelloAsso.
- AC : KPI cards : Total produits / Total en stock / En alerte / Ventes du jour.

**US-BUVETTE-3** — *En tant qu'AdminBénévoles, je veux ajuster manuellement le stock d'un produit (réassort physique).*
- AC : bouton "Ajuster" sur chaque carte produit.
- AC : modale avec quantité actuelle + nouvelle quantité, seuil d'alerte, emoji.
- AC : enregistrement met à jour `quantity` ; reset `alert_sent` si quantité repasse au-dessus du seuil.

**US-BUVETTE-4** — *En tant que Super Admin, je veux que chaque vente HelloAsso décrémente automatiquement notre stock.*
- AC : endpoint webhook public `POST /api/v1/buvette/webhook/helloasso` reçoit les notifications HelloAsso.
- AC : sur eventType `Order` ou `Payment` (avec data.order), pour chaque item de la commande :
  - vérification d'idempotence sur `(payment_id, item_id)` ;
  - décrémente `quantity` du `BuvetteProduct` correspondant à `tierId` ;
  - log la vente dans `BuvetteSales` avec snapshot du nom, infos client (firstname/lastname/email), montant.
- AC : si `quantity < seuil_alerte` ET `alert_sent=false` → email aux AdminBenevoles + Super Admin, flag à true.
- AC : retourne toujours `200 {"status":"ok"}` pour éviter les retries HelloAsso (sauf payload malformé → 422).

**US-BUVETTE-5** — *En tant que Super Admin, je veux activer ou désactiver le webhook HelloAsso depuis l'app.*
- AC : modale "Webhook" affiche le statut courant (`GET /v5/organizations/{slug}/notifications`).
- AC : bouton "Activer" → `PUT` chez HelloAsso avec l'URL `https://stock.lekouttab.fr/api/v1/buvette/webhook/helloasso`.
- AC : bouton "Désactiver" → `DELETE` chez HelloAsso.
- AC : si la sync ou la config échoue (HelloAsso indisponible), message d'erreur clair affiché.

**US-BUVETTE-6** — *En tant qu'AdminBénévoles ou Compta, je veux consulter l'historique des ventes de la buvette.*
- AC : page `/buvette/sales` avec table paginée (50 par page).
- AC : colonnes : Date, Produit, Quantité, Montant, Client, Référence commande HelloAsso.
- AC : tri par défaut : plus récent en premier.

**US-ADMIN-4** — *En tant que Super Admin, je veux exporter/importer la base via CSV.*
- AC : bouton Export → ZIP de tous les CSVs (sauf Admins pour sécurité), nommage horodaté.
- AC : Import → checkbox de confirmation obligatoire, multi-upload CSV, rapport par table.
- AC : page diagnostic affiche état (fichier OK, tables, lignes, taille).

### 2.4 Non-Goals (Buvette HelloAsso)

- Pas de **modification** des produits ou prix HelloAsso depuis notre app — HelloAsso reste le SoT pour le catalogue commercial.
- Pas de **gestion des paiements / remboursements** HelloAsso — déjà géré côté HelloAsso.
- Pas de **réconciliation des stocks** HelloAsso ↔ notre app — chaque côté garde sa source de vérité (HelloAsso = caisse / nous = stock physique).
- Pas de **vente offline** depuis notre app (pas de POS embarqué) — la buvette physique passe toujours par HelloAsso pour encaisser.

### 2.3 Non-Goals

- Pas d'application mobile native — la SPA web responsive est suffisante.
- Pas de SSR / SEO — application interne accessible uniquement après login.
- Pas de notifications push / SMS — les emails suffisent.
- Pas d'OCR sur tickets / factures.
- Pas de signature électronique des justificatifs.
- Pas de multi-tenant (1 association = 1 instance).
- Pas d'intégration comptable externe (Pennylane, Sage…) — export CSV reste manuel.
- Pas de soft-delete : le legacy hard-delete est conservé pour l'instant.

---

## 3. AI System Requirements

**Non applicable.** L'application n'embarque pas de fonctionnalité IA. (Possible évolution v3 : OCR de tickets, classification automatique des dépenses — voir Roadmap.)

---

## 4. Technical Specifications

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Browser (React SPA)                                    │
│  - Vite + React 18 + TS + Tailwind                      │
│  - TanStack Query, React Hook Form, Zustand             │
│  - Auth: JWT in localStorage + refresh rotation         │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTPS (Authorization: Bearer …)
                   │ JSON / multipart
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Apache (.htaccess) on stock.lekouttab.fr               │
│  - SPA fallback (React Router)                          │
│  - Proxy /api → Passenger Python app                    │
│  - Headers: HSTS, CSP, X-Frame-Options                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Passenger Python 3.11 (cPanel)                         │
│  passenger_wsgi.py → a2wsgi → FastAPI ASGI app          │
│  - Routers /api/v1/{auth,users,stock,expenses,…}        │
│  - Middleware: CORS, rate-limit, request logging        │
│  - Dependencies: JWT auth, role guards                  │
└──────┬──────────────────────────────────────┬───────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────────────┐       ┌─────────────────────┐
│  MySQL O2Switch          │       │  uploads/ on disk   │
│  sc9bewu6999_stock       │       │  protégés .htaccess │
│  10 tables, FK CASCADE   │       │  servis via API     │
└──────────────────────────┘       └─────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  SMTP O2Switch (mail.lekouttab.fr:465 TLS)              │
│  via fastapi-mail (BackgroundTasks pour async)          │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Integration Points

| Système | Protocole | Usage | Auth |
|---|---|---|---|
| MySQL O2Switch | TCP 3306 | Persistance | username/password en `.env` |
| SMTP O2Switch | TLS 465 | Envoi emails (alertes, notifications, invitations) | login SMTP |
| Filesystem O2Switch | local | Stockage uploads | filesystem perms 750 |
| **HelloAsso API V5** (sortant) | HTTPS | Sync des produits buvette (`GET /v5/organizations/{slug}/forms/Shop/{form}/public`), config webhook (`PUT /v5/organizations/{slug}/notifications`) | OAuth2 client_credentials (token cache 30 min, refresh 30 j) |
| **HelloAsso webhook** (entrant) | HTTPS POST | Notification de chaque commande / paiement de la buvette | endpoint public, idempotence DB |

### 4.3 Security & Privacy

| Aspect | Implémentation |
|---|---|
| **Auth** | JWT HS256, access 30 min, refresh 7 jours avec rotation |
| **Hash mdp** | bcrypt (cost 12) ; migration progressive depuis SHA256 |
| **Validation mdp** | 8+ chars, maj, min, chiffre, symbole (signup + admin-setup) |
| **Rate limit** | slowapi : login 5/15min, signup 3/h, par IP |
| **Lockout** | 5 échecs login → lockout 15 min (table `LoginAttempts`) |
| **Tokens invitation** | `secrets.token_urlsafe(32)`, hash SHA256 stocké, expiration 24 h, max 3 tentatives |
| **HTTPS** | Forcé par O2Switch + HSTS preload |
| **CSP** | `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'` |
| **CORS** | Origin strict en prod (`https://stock.lekouttab.fr`) |
| **CSRF** | Non applicable (API JWT stateless ; pas de cookies de session) |
| **XSS** | React échappe par défaut ; Pydantic valide les entrées |
| **SQLi** | SQLAlchemy paramétré ; jamais de SQL string concat |
| **File upload** | Whitelist MIME via magic bytes + extension ; UUID filename ; 10 Mo max |
| **Données sensibles** | Champs `email`, `telephone`, `rib` : journalisation masquée ; `password_hash` jamais retourné par l'API |
| **RGPD** | Utilisateurs peuvent demander la suppression (Super Admin exécute) ; pas de tracking analytics ; logs purgés après 90 jours |
| **Backups** | Export ZIP manuel par Super Admin ; cron O2Switch `mysqldump` quotidien recommandé (à mettre en place) |
| **Audit** | Table `StockModifications` trace les changements de stock ; pas d'audit log global pour MVP |

### 4.4 Performance & Scalability

- **Charge prévue** : < 50 utilisateurs simultanés, < 100 req/min en pic.
- **Pool de connexions DB** : 5 connexions, recycle 1 h (O2Switch ferme les inactives).
- **Cache front** : assets immuables (`hash` Vite) avec `Cache-Control: max-age=31536000, immutable` ; `index.html` `no-cache`.
- **Cache API** : pas de cache HTTP au MVP ; TanStack Query fait le cache côté client (5 min staleTime sur catégories/utilisateurs).
- **Optimistic updates** côté front pour les actions rapides (toggle statut, approbation modif).

### 4.5 Compatibility

| Cible | Support |
|---|---|
| **Navigateurs** | Chrome / Edge / Firefox / Safari dernières 2 versions |
| **Devices** | Desktop ≥ 1280×720 ; mobile ≥ 360×640 (responsive) |
| **OS** | Windows / macOS / iOS / Android (web) |
| **Accessibilité** | WCAG 2.1 AA cible (niveau 95+ Lighthouse) |

---

## 5. Risks & Roadmap

### 5.1 Technical Risks

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| **Passenger O2Switch limite mémoire / restarts intempestifs** | Moyenne | Haut | Ajouter health endpoint + monitoring externe ; charger lazy les imports lourds |
| **Migration hash SHA256 → bcrypt mal vécue** | Moyenne | Moyen | Flag `password_must_change` + reset auto au prochain login + email d'avertissement |
| **Perte de données pendant la bascule** | Faible | Critique | Backup MySQL complet **avant** premier déploiement ; Alembic `stamp head` (no-op) ; rollback plan documenté |
| **SMTP O2Switch indisponible** | Faible | Moyen | Try/except + log d'erreur + retry 3× ; dégradation gracieuse (action OK même si email échoue) |
| **Upload de fichier malicieux** | Moyenne | Haut | Magic bytes + whitelist MIME + UUID filename + servis derrière endpoint authentifié |
| **JWT en localStorage volé via XSS** | Faible | Haut | React échappe par défaut + CSP stricte + pas de `dangerouslySetInnerHTML` |
| **Endpoint d'invitation utilisé en brute-force** | Moyenne | Moyen | Rate limit + lockout token après 3 essais + expiration 24 h |
| **HelloAsso API indisponible** (sync ou webhook config) | Faible | Moyen | Try/except + message UI clair ; le webhook sortant chez HelloAsso reste actif même si notre sync échoue |
| **Webhook HelloAsso reçu en double / out-of-order** | Élevée (HelloAsso retry agressivement) | Faible (mitigé) | UNIQUE `(payment_id, item_id)` côté DB → décrément exécuté une seule fois ; logger en cas de doublon |
| **Token HelloAsso expiré non renouvelé** | Moyenne | Moyen | Service maintient son token en mémoire avec `_expires_at` ; refresh automatique ; renouveau via client_credentials si refresh > 30 j |
| **Webhook public ouvert à l'extérieur** | Moyenne | Faible | Validation Pydantic stricte ; idempotence DB ; rate-limit 60 req/min ; v1.1 : whitelist IP HelloAsso ou signature HMAC |

### 5.2 Phased Rollout

#### **MVP (v1.0) — 4-6 semaines**
*Périmètre : équivalence fonctionnelle au legacy Streamlit.*
- ✅ Auth (login, signup, JWT, lockout)
- ✅ Dashboard (vue + historique + alertes + modifications en attente)
- ✅ Stock (navigation 3 niveaux, modif directe + demande, CRUD admin, import CSV)
- ✅ Notes de frais (soumission, édition, validation compta, fichiers)
- ✅ Factures (dépôt, listing, validation)
- ✅ Admin (validation comptes, gestion users, gestion catégories)
- ✅ Export/Import BDD (Super Admin)
- ✅ Emails (alertes stock, nouvelle note de frais, factures)
- ✅ **Buvette HelloAsso : sync produits, webhook ventes, page consultation, ajustement stock manuel**
- ✅ Déploiement O2Switch

**Critères de succès MVP** : tous les utilisateurs migrés, zéro perte de données, support 1ʳᵉ semaine ≤ 5 tickets.

#### **v1.1 — +2 semaines**
- Invitations admin par email (workflow complet)
- Tableau de bord enrichi : graphes Recharts au lieu des barres natives
- Notifications in-app (toast lors changement de statut de mes notes/factures)
- Profil utilisateur : changement de mot de passe self-service
- Mobile UX raffinée (bottom nav)

#### **v1.2 — +3 semaines**
- Chiffrement RIB au repos (AES-256, key dans `.env`)
- Audit log global (table `AuditLog`) pour les actions sensibles
- Backups MySQL automatiques (cron O2Switch + S3 externe)
- Rapport PDF des dépenses par période (jsPDF / WeasyPrint)
- Multi-fichiers drag & drop avec aperçu

#### **v2.0 — exploratoire**
- OCR sur tickets de caisse (Tesseract en self-hosted ou API externe)
- Catégorisation automatique des dépenses (modèle ML simple)
- API publique pour intégration avec outil comptable
- Notifications push (Web Push API)
- Mode hors ligne PWA pour saisie de notes

---

## 6. Open Questions & Assumptions

### Questions ouvertes
1. **Q1** : Conserve-t-on les anciens comptes Streamlit ou recrée-t-on tout le monde ? *(Hypothèse : conserver, avec migration password forcée au prochain login.)*
2. **Q2** : Le RIB doit-il être chiffré dès le MVP ou v1.2 ? *(Hypothèse : v1.2 ; en MVP, l'accès est restreint par rôle.)*
3. **Q3** : Backups quotidiens mysqldump : à mettre en place côté O2Switch (cPanel cron) ou côté FastAPI (BackgroundTask) ? *(Hypothèse : O2Switch cron — moins de complexité applicative.)*
4. **Q4** : Domaine `stock.lekouttab.fr` actuellement redirigé vers Streamlit Cloud — la bascule se fait quand exactement ? *(Hypothèse : un weekend, fenêtre 2 h, communication 1 semaine avant.)*
5. **Q5** : Faut-il garder la possibilité de logger en SQLite local pour le développement ? *(Hypothèse : non, dev pointe sur MySQL distant ou Docker MySQL local — simplifie le code.)*

### Assumptions
- Les credentials O2Switch (FTP, MySQL, SMTP) sont fournis par le client.
- Le node_modules ne sera **jamais** uploadé sur O2Switch ; build local + upload `dist/`.
- Python 3.11 est bien disponible dans cPanel (à vérifier au démarrage).
- Pas plus de 10 utilisateurs admins simultanés (donc pas besoin de Redis pour le rate-limit en MVP, in-memory suffit).
- Volume de fichiers uploads < 5 Go en cumul (pas de pression de stockage O2Switch).

---

## 7. Analytics & Monitoring

| Métrique | Outil | Alertes |
|---|---|---|
| Uptime | UptimeRobot ou Better Stack (ping `/api/v1/health` toutes les 5 min) | Email Super Admin si down ≥ 5 min |
| Erreurs serveur | Sentry SaaS (free tier) | Slack/email si nouvelle exception |
| Logs applicatifs | Fichiers `backend/logs/app.log` (rotation 10 Mo, 7 fichiers) | — |
| Logs sécurité | Fichiers `backend/logs/security.log` | Audit manuel mensuel |
| Performance API | Middleware FastAPI logguant durée par endpoint | Alerte si p95 > 500 ms |
| Espace disque uploads | Cron mensuel `du -sh uploads/` → email Super Admin | — |

---

## 8. Release Planning

| Phase | Date estimée | Livrables |
|---|---|---|
| **Kickoff** | semaine 0 | PRD validé, accès O2Switch, backup MySQL initial |
| **Sprint 1** | sem. 1-2 | Backend : modèles + auth + stock + expenses + invoices |
| **Sprint 2** | sem. 3-4 | Frontend : auth + dashboard + stock + expenses + invoices |
| **Sprint 3** | sem. 5 | Admin pages, emails, export/import, tests E2E |
| **Sprint 4** | sem. 6 | Déploiement O2Switch staging, recette client, fixes |
| **Go-live MVP** | fin sem. 6 | Bascule production, monitoring activé |
| **v1.1** | sem. 7-8 | Améliorations UX + invitations |
| **v1.2** | sem. 9-11 | Sécurité (chiffrement RIB, audit log), backups |

---

## 9. Appendix

### 9.1 Glossaire
- **AdminBénévoles** : rôle de gestion logistique (stock).
- **Compta** : rôle financier (validation notes/factures).
- **Note de frais** : demande de remboursement par un bénévole.
- **Facture** : document tiers (fournisseur) déposé pour traitement.
- **Modification de stock** : demande/action de mise à jour de la quantité d'un article.
- **RIB / IBAN** : coordonnées bancaires utilisées pour les remboursements.

### 9.2 Références
- Code legacy : `../` (parent directory)
- Schéma SQL : `../create_mysql_structure.sql`
- Guide PRD : `prd-guide.md`
- Conventions techniques : `CLAUDE.md`
- Mémoire stable : `memory.md`

### 9.3 Compétiteurs / inspirations
- **Lokad / Erplain** : trop lourds et payants pour une asso.
- **AirTable** : flexible mais pas de workflow validation natif.
- **Notion + formulaires** : pas de gestion de quantités/alertes.
*Décision* : développement sur-mesure justifié par la spécificité du flow validation + RIB + invitations.
