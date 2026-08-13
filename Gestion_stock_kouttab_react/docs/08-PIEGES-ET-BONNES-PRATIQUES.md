# Pièges connus et bonnes pratiques

Ce document ne décrit pas le code : il décrit **les erreurs qui ont réellement
été commises sur ce projet**, ce qu'elles ont coûté, et la règle qu'on en tire.

Chaque entrée part d'un incident vérifiable. C'est volontaire — une règle sans
son incident se discute et finit par sauter ; une règle avec son incident se
comprend.

---

## 1. Les règles absolues

Trois règles n'admettent aucune exception. Les enfreindre a déjà causé des
dégâts durables.

### Ne jamais enchaîner les tentatives SSH vers le VPS

`fail2ban` y bannit l'adresse IP après quelques échecs d'authentification, et
**le bannissement survit au redémarrage**. Le 2026-08-11, neuf essais pour
trouver la bonne clé ont coupé le port 22 à tout le bureau, opérateur compris.
Le serveur fonctionnait ; plus personne ne pouvait s'y connecter.

**Au premier `Permission denied (publickey)`, s'arrêter et demander.** Le remède
passe par la console distante IONOS — procédure dans `DEPLOIEMENT-VPS.md` §0.

### `RIB_ENCRYPTION_KEY` ne se perd pas

Elle vit uniquement dans le `.env` du VPS (mode 600, propriétaire `deploy`),
jamais dans le dépôt. **La perdre rend tous les RIB définitivement illisibles** :
il n'existe aucun moyen de les retrouver. Son absence empêche le démarrage en
production, et c'est voulu.

### La suite de tests n'écrit à personne

Le `.env` de développement porte les identifiants de la messagerie réelle de
l'association. La suite a longtemps arrosé la boîte de la comptabilité de
fausses factures — « [Facture] EV(T) — Gala d'été 2026 » — à chaque exécution,
plusieurs fois par jour.

Deux protections cumulées, et `tests/unit/test_aucun_envoi_reel.py` existe pour
qu'aucune des deux ne puisse sauter. Cf. `docs/07-TESTS.md`.

---

## 2. La classe de bug la plus coûteuse : un affichage qui ment

Trois incidents distincts, la même cause. C'est le piège dominant de ce projet.

### Le champ d'événement qui n'apparaissait jamais

`EventSelect` déduisait l'affichage du champ de saisie libre **de la valeur déjà
saisie** :

```ts
const value = eventId !== null ? String(eventId) : freeText ? FREE_EVENT : '';
{(value === FREE_EVENT || isError) && <Input … />}
```

Choisir « Mon événement n'est pas dans la liste » appelait `onFreeTextChange('')`.
Au rendu suivant, `freeText` était vide, donc `value` retombait à `''`, donc le
champ **n'apparaissait jamais**. Le formulaire réclamait alors un événement
qu'aucun champ ne permettait d'entrer : le dépôt était bloqué.

Correctif : un état local `modeLibre`, indépendant du contenu saisi.

### Le statut qui affichait « Approuvée » et envoyait « Remboursée »

Pour masquer une valeur devenue absente de la liste, l'écran affichait une
valeur et le formulaire en gardait une autre :

```tsx
value={form.watch('status') === 'Remboursée' ? 'Approuvée' : form.watch('status')}
```

Cliquer sur « Mettre à jour » sans toucher à la liste renvoyait donc le statut
**inchangé**. Le serveur l'acceptait comme un non-changement, et le message
« Statut mis à jour » s'affichait pendant que rien ne bougeait. Une confirmation
mensongère, pire qu'une erreur.

### Le fichier envoyé étiqueté « JSON »

L'instance axios pose `Content-Type: application/json` par défaut, ce qui écrase
la détection d'axios. Un `FormData` partait sans sa frontière (`boundary`), le
serveur ne parvenait pas à le découper, et rendait un `VAL_5001` que rien
n'expliquait à l'écran. Cinq appels rétablissaient l'en-tête à la main ; le
sixième, écrit plus tard, l'avait oublié.

Correctif structurel : l'intercepteur retire l'en-tête dès que le corps est un
`FormData` — on supprime la classe de bug, pas le cas.

> **La règle.** Un affichage ne doit jamais contredire ce qui sera soumis. Si
> une valeur affichée diffère de la valeur envoyée, c'est un bug, même quand
> l'intention est bonne. Et quand le même oubli est possible à six endroits,
> corriger le sixième ne suffit pas : il faut retirer la possibilité.

---

## 3. Un succès qui n'en est pas un

### L'envoi désactivé qui s'affichait « Envoyé »

`_send_raw` retournait en silence quand `EMAIL_ENABLED=false`, « pour que le
circuit comptable se déroule jusqu'au bout ». `outbox._deliver` interprétait ce
retour comme une livraison et marquait la ligne **`sent`**, horodatage compris.

La production a tourné ainsi : écran des envois **tout en vert**, boîtes vides.
Ni les pièces au comptable, ni les changements de statut, ni les relances de
justificatifs ne partaient. Aucun signal nulle part.

> **La règle.** « Ne rien faire » et « avoir réussi » ne peuvent pas se dire de
> la même façon. Un état qui se trompe dans le sens rassurant est plus dangereux
> qu'une panne franche : il supprime le signal qui aurait déclenché l'enquête.

Correctif : l'envoi désactivé **lève**, la ligne apparaît en échec avec son
motif, et `GET /admin/outbound-emails/etat` dit l'état du circuit avant même
qu'un envoi soit tenté — une file vide et un serveur coupé se ressemblaient trop.

---

## 4. Deux chemins vers le même état, un seul complet

### « Remboursée » se constatait, ou se déclarait

Le bouton « Rembourser » enregistrait le versement — date, moyen, établissement,
approbation — et produisait le justificatif PDF et tableur. La liste déroulante
de l'écran comptable posait **le même statut sans rien produire**.

Des notes se sont donc retrouvées marquées payées sans document, absentes de
l'onglet « Remboursements ». Et comme le statut était terminal, aucune
transition ne permettait de revenir en arrière pour faire les choses
correctement : la note était bloquée.

> **La règle.** Quand un état est la conséquence d'un fait, il ne doit pas être
> déclarable par ailleurs. Et tout état terminal a besoin d'une porte de sortie
> pour les lignes qui y sont entrées par erreur.

Correctif : « Remboursée » ne figure dans aucune cible du graphe de transitions ;
le retour vers « Approuvée » reste ouvert **tant qu'aucun versement n'est
rattaché**.

---

## 5. Les fonctionnalités qui vont par paire

### Écarter un justificatif sans pouvoir en redéposer un

Aucun endpoint ne permettait d'ajouter une pièce à une note déjà créée :
`attach_file` n'était appelé qu'à la création, et l'écran conseillait même de
« supprimer cette note et la recréer ». Livrer l'écart seul aurait laissé des
notes sans justificatif et **sans aucun recours** — l'écran serait devenu un
piège.

> **La règle.** Avant d'ajouter un geste qui retire quelque chose, vérifier
> qu'il existe un geste qui le remet. Sinon, les deux se livrent ensemble ou
> aucun des deux.

Même raisonnement pour l'archivage : il n'a été livré qu'avec sa restauration.

---

## 6. Conserver plutôt que détruire

Trois destructions ont été retirées du code, pour la même raison : une pièce
comptable se conserve plusieurs années, et rien ne justifie qu'un clic la fasse
disparaître.

| Geste d'origine | Ce qu'il détruisait | Remplacé par |
|---|---|---|
| `DELETE /expenses/{id}` | la note et ses justificatifs, base et disque | archivage réversible |
| `DELETE /invoices/{id}` | la facture, ses fichiers, leur contenu — **sur n'importe quel statut, « Validée » comprise** | archivage réversible |
| suppression d'un justificatif | — (n'existait pas) | écart réversible, avec motif |

Une **suppression définitive** subsiste, à la demande explicite du client, pour
les notes de test et les erreurs avérées : Super Admin uniquement, motif
obligatoire journalisé, confirmation explicite. C'est l'exception, et elle est
outillée comme telle.

> **La règle.** Ranger, pas détruire. Et quand la destruction est légitime, la
> réserver au plus petit cercle possible, exiger un motif, et le journaliser
> avant d'agir — c'est la seule trace qui restera.

---

## 7. La base est la seule copie sauvegardée

O2Switch sauvegarde la base ; **le volume Docker du VPS n'est pas sauvegardé**.
Tout document qui n'existe que sur ce volume disparaît avec la machine.

Trois familles de documents y ont migré, dans cet ordre : les justificatifs de
notes et de factures, le RIB en document, puis les justificatifs de
remboursement — les derniers restés dehors, et on s'en est aperçu tardivement.

Deux conséquences pratiques :

- toute colonne de contenu est **`deferred=True`**. Sans cela, lister les notes
  de frais rapatrierait tous les octets de tous les justificatifs depuis une
  base distante ;
- `chemin_fichier` reste renseigné, mais comme **cache** et trace d'origine. Ce
  qui exige un chemin passe par `files.materialiser`, qui réécrit le fichier
  depuis la base au besoin.

---

## 8. Les modules jumeaux

Deux paires doivent être modifiées **ensemble** :

| Backend | Frontend | Ce qu'ils décident |
|---|---|---|
| `services/naming.py` | `lib/naming.ts` | le nom de la pièce envoyée au comptable |
| `core/money.py` | `lib/money.ts` | le montant dû au bénévole |

Elles partagent une table de cas de test : modifier l'une sans l'autre **casse
un test**, et c'est voulu. Le front affiche le nom et le montant, le back les
grave dans le document envoyé — corriger l'un seul produit une pièce qui
contredit l'écran l'ayant déclenchée.

---

## 9. La base est distante

MySQL/MariaDB chez O2Switch, jointe par tunnel depuis le VPS. **Chaque requête
coûte un aller-retour réseau.** Cela dicte plusieurs choix qu'on prendrait
autrement en local :

- se méfier des endpoints qui enchaînent les requêtes, et du chargement paresseux
  des relations — préférer `selectinload` ;
- filtrer et compter **côté client** quand les données sont déjà chargées : c'est
  le parti des écrans de notes de frais et de factures, qui rapatrient tout une
  fois puis répartissent localement ;
- dans une migration qui écrit dans l'existant, procéder **par lots** : un
  `UPDATE` par ligne se compte en minutes, avec le risque d'une coupure au
  milieu.

---

## 10. Les migrations

Le schéma est partagé avec la production. Toute migration s'exécute sur des
données réelles.

- **Sauvegarder avant** toute migration qui écrit dans les lignes existantes.
  Ajouter une colonne vide est sans risque ; renseigner cette colonne pour
  chaque ligne ne l'est pas.
- **Mesurer avant d'écrire.** La migration `f6b3d1e8a295` contrôle
  `max_allowed_packet` *avant* de charger le moindre fichier : une migration
  interrompue au milieu laisserait la moitié des pièces en base et l'autre sur
  le disque, sans que rien ne dise laquelle est laquelle.
- **Ordre stable.** Quand une migration numérote ou trie, départager par `id`
  pour que la rejouer sur une copie donne exactement le même résultat.
- **Amorcer les compteurs.** Une migration qui remplit une table de séquence
  doit la positionner au dernier rang attribué. L'oublier fait repartir le
  compteur à 1 au premier usage, et heurter la contrainte d'unicité — panne
  immédiate, en production, sur le geste le plus courant.
- Vérifier `POST /admin/database/import` et `/export` : ils manipulent les
  colonnes directement et cassent en silence quand le schéma bouge.

---

## 11. Ce que les tests n'attrapent pas

Constat honnête sur ce projet : **plusieurs régressions livrées ont été trouvées
par le client, pas par la suite de tests**, alors que celle-ci passait
intégralement à chaque fois.

Le point commun : les tests vérifiaient l'intention du développeur, pas le geste
de l'utilisateur. Un formulaire dont l'affichage ment passe tous les tests
unitaires du composant. Un bouton devenu invisible parce qu'un filtre par défaut
a changé ne casse aucune assertion.

> **La règle.** Après un changement d'écran, refaire le geste réel dans
> l'application. La suite de tests dit que le code fait ce qu'on lui a demandé ;
> elle ne dit pas qu'on lui a demandé la bonne chose.

Les points à vérifier à la main sont listés dans `docs/07-TESTS.md`.

---

## 12. Conventions d'écriture

### Commentaires

Un commentaire dit **pourquoi**, jamais **quoi** — le code dit déjà quoi. Les
commentaires les plus utiles de ce dépôt racontent l'incident qui a motivé la
ligne. C'est ce qui empêche quelqu'un de « simplifier » six mois plus tard une
protection dont il ignore l'origine.

Exemple, dans `compta_dispatch` : le chemin de conversion PDF subsiste bien que
le contenu soit désormais déjà un PDF, parce qu'il reste indispensable pour
renvoyer une pièce ancienne. Sans le commentaire, il serait pris pour du code
mort.

### Tests

Nom en français décrivant le comportement, docstring disant quel défaut réel le
test empêche de revenir. `test_la_file_marque_l_echec_et_non_l_envoi` se lit ;
`test_deliver_returns_false` ne dit rien.

### Texte affiché

Tout passe par `frontend/src/lib/i18n/fr.ts`. Un message d'erreur s'adresse à un
bénévole, pas à un développeur : « Extension 'heic' non autorisée (attendu :
jpeg, jpg, pdf, png) » a été remplacé par une phrase qui dit quoi faire.

---

## Voir aussi

- `docs/01-ARCHITECTURE.md` — les couches et les parcours
- `docs/06-ENVIRONNEMENTS-ET-DEPLOIEMENT.md` — les pièges propres au déploiement
- `docs/07-TESTS.md` — comment tester, et ce que les tests ne couvrent pas
- `DEPLOIEMENT-VPS.md` — la procédure d'exploitation détaillée
