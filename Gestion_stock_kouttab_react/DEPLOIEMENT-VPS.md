# Mise en production — VPS IONOS + base O2Switch

Cible : **VPS IONOS, Ubuntu 24.04**, `85.215.168.239`, domaine `stock.lekouttab.fr`.
La **base MySQL reste chez O2Switch** ; le VPS n'héberge que le front et l'API.

> `DEPLOIEMENT.md` documente l'ancienne cible (O2Switch / Passenger). Il est
> conservé pour l'historique mais n'est plus la procédure en vigueur.

## ⚠️ Le VPS est mutualisé — lire `/opt/CLAUDE.md` sur le serveur

Cette machine héberge **plusieurs projets indépendants**, dont
`question.lekouttab.fr`, en production. Le serveur porte sa propre
documentation, `/opt/CLAUDE.md`, qui fait autorité sur tout ce qui suit :

```bash
ssh <compte>@85.215.168.239 'cat /opt/CLAUDE.md'
```

### L'architecture à deux étages

```
   Internet ──443──▶  infra-caddy  ──┬──▶ kouttab-stock-web
                      /opt/infra     ├──▶ kouttab-stock-api
                      ports 80/443   └──▶ kouttab-questions-…
                                          réseau Docker `web`
```

| Étage | Chemin | Qui y touche |
|---|---|---|
| **Socle** | `/opt/infra` | intervention rare, impacte **tous** les projets |
| **Projets** | `/opt/projets/<nom>` | chaque projet, indépendamment |

**Ce que cela impose à ce projet** — c'est déjà appliqué dans `compose.yml` :

1. **Aucun `ports:`.** Un unique Caddy détient 80 et 443 pour la machine
   entière. Une version antérieure de ce fichier embarquait son propre Caddy
   publiant ces ports : la déployer telle quelle aurait mis
   `question.lekouttab.fr` hors ligne.
2. **Réseau `web` en `external: true`.** Sans cela, Compose crée un réseau isolé
   et Caddy ne voit jamais nos conteneurs — symptôme : `502 Bad Gateway`.
3. **`container_name` préfixés** (`kouttab-stock-api`, `kouttab-stock-web`) :
   Caddy résout les conteneurs par leur nom, deux projets nommant leur service
   `api` entrent en collision.
4. **Jamais de `docker compose down -v` dans `/opt/infra`** : le volume
   `caddy_data` contient les certificats TLS de *tous* les projets.

### La base n'a pas besoin de tunnel

`85.215.168.239` est **déjà** autorisée dans cPanel → *Bases de données* →
*MySQL distant*, et tous les conteneurs du VPS sortent avec cette IP. La
connexion à `sauterelle.o2switch.net:3306` est directe. Le service `db-tunnel`
a été retiré du `compose.yml` : il répondait à un besoin qui n'existe pas ici.

## Ce qui change

| | Avant (O2Switch) | Maintenant |
|---|---|---|
| Build du front | à la main, en local | GitHub Actions |
| Livraison | FTP | images GHCR + `docker compose` |
| Serveur web | Apache + `.htaccess` | Caddy **du socle** + nginx |
| Process Python | Passenger WSGI | uvicorn en conteneur |
| Cron comptable | cron cPanel | service `outbox-worker` |
| Base MySQL | locale au serveur | **distante, accès direct autorisé par IP** |
| Sauvegarde base | O2Switch | **O2Switch (inchangé)** |
| Sauvegarde `uploads/` | O2Switch | **à ta charge — §11** |

---

## 0. Avant de toucher à SSH — lire ceci

> **Une tentative de connexion échouée coûte cher.** `fail2ban` surveille le
> port 22 et bannit l'adresse IP au bout de quelques échecs d'authentification.
> Le bannissement **survit au redémarrage** : il est conservé dans
> `/var/lib/fail2ban/fail2ban.sqlite3` et rejoué au démarrage du service.
>
> C'est arrivé le 2026-08-11 : neuf essais successifs pour trouver la bonne clé
> ont fermé le port 22 à toute l'adresse IP du bureau — poste de l'opérateur
> compris. Le serveur tournait parfaitement (Caddy répondait sur 80 et 443),
> mais plus personne ne pouvait s'y connecter, et redémarrer n'y a rien changé.
>
> **La règle : au premier `Permission denied (publickey)`, on s'arrête.**
> Essayer une deuxième clé « pour voir » consomme un essai sur le compteur.
> Chercher d'abord quelle clé est censée ouvrir ce serveur — voir §7, la clé de
> déploiement vit dans le secret GitHub `VPS_SSH_KEY`, pas forcément sur le
> poste.

### Symptôme et remède

Port 22 muet alors que 80/443 répondent : c'est un bannissement, pas une panne.
`fail2ban` ne filtre que le service concerné, le reste du serveur reste servi.

```bash
# Diagnostic depuis le poste : 22 injoignable, 80/443 ouverts => banni.
for p in 22 80 443; do
  timeout 5 bash -c "echo > /dev/tcp/<IP_DU_VPS>/$p" 2>/dev/null \
    && echo "port $p ouvert" || echo "port $p injoignable"
done
```

Deux portes de sortie, dans cet ordre :

1. **La console distante IONOS** (panneau → serveur → « Console distante »).
   Elle ne passe pas par le réseau SSH : elle fonctionne même banni. C'est la
   seule voie fiable.
2. **Une autre adresse IP** (partage de connexion mobile, autre réseau) : le ban
   porte sur l'IP, pas sur le compte.

Puis, une fois connecté — `fail2ban-client` exige les droits root :

```bash
sudo fail2ban-client status sshd            # liste les IP bannies
sudo fail2ban-client set sshd unbanip <IP>  # lève le bannissement
```

> `root` n'est pas joignable en SSH une fois le §1 appliqué
> (`PermitRootLogin no`) : c'est voulu. Passer par un compte sudoer.
> Et `sudo echo ... >> fichier` **n'écrit rien** — la redirection est exécutée
> par le shell appelant, qui n'est pas root. Utiliser `| sudo tee -a`.

---

## 1. Durcir le VPS (à faire en premier)

Connexion initiale en `root`, puis on referme derrière soi.

```bash
ssh root@85.215.168.239
passwd                                   # changer le mot de passe initial IONOS

adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
```

Depuis **ton poste**, générer la clé de déploiement et l'installer :

```bash
ssh-keygen -t ed25519 -C "deploy@kouttab" -f ~/.ssh/kouttab_deploy
ssh-copy-id -i ~/.ssh/kouttab_deploy.pub deploy@85.215.168.239
ssh -i ~/.ssh/kouttab_deploy deploy@85.215.168.239   # doit fonctionner AVANT la suite
```

Une fois la connexion par clé vérifiée — et pas avant, sous peine de se
verrouiller dehors :

```bash
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'            /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable

sudo apt update && sudo apt install -y fail2ban unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

## 2. Installer Docker

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy      # se reconnecter pour que le groupe prenne effet
```

## 3. Déposer les fichiers

Le projet vit dans `/opt/projets/`, à côté des autres — jamais dans `/opt`
directement, et **jamais dans `/opt/infra`**, qui appartient au socle.

```bash
sudo mkdir -p /opt/projets/kouttab-stock
sudo chown "$USER:$USER" /opt/projets/kouttab-stock
cd /opt/projets/kouttab-stock

# Seuls compose.yml, deploy/ et le .env sont nécessaires ici : le code
# applicatif arrive par les images GHCR.
git clone --depth 1 <URL_DU_DEPOT> repo
cp repo/Gestion_stock_kouttab_react/compose.yml .
cp -r repo/Gestion_stock_kouttab_react/deploy .
cp repo/Gestion_stock_kouttab_react/.env.deploy.example .env
chmod 600 .env
```

> Le `Caddyfile` du projet n'est **pas** copié : le TLS et le routage sont
> assurés par le Caddy du socle. Notre seule contribution au routage est le
> fragment `deploy/site.caddy`, déposé au §9.

Le compte qui pilote Docker doit appartenir au groupe `docker` — sinon chaque
commande répond `permission denied ... docker.sock` :

```bash
sudo usermod -aG docker "$USER"    # puis se déconnecter/reconnecter
```

## 4. Mesurer la latence vers O2Switch

À faire **avant** la bascule : c'est ce chiffre qui dira si l'architecture tient.

```bash
ping -c 10 <hôte_o2switch>          # < 15 ms : bien. 15-30 ms : acceptable. > 40 ms : à discuter.
```

IONOS a des datacenters en Allemagne et en France. Si la latence dépasse 40 ms,
il vaut mieux recréer le VPS dans une région française que d'optimiser le code.

## 5. Joindre la base O2Switch

### 5.1 Autoriser l'IP du VPS (obligatoire)

cPanel → **MySQL distant** (*Remote MySQL*) → ajouter `85.215.168.239`.

Sans cette autorisation, le serveur refuse **avant** l'authentification : le
message parle d'un hôte non autorisé, pas d'un mot de passe invalide.

En développement depuis ton poste, il faut aussi y ajouter l'IP de ta box — qui
change à chaque redémarrage du routeur.

### 5.2 Les trois pièges du `.env`

Éprouvés sur les autres applications de l'association, par ordre de fréquence :

1. **`DB_HOST` = le nom du cluster** relevé dans cPanel (ex.
   `sauterelle.o2switch.net`). Surtout pas `localhost` : la base n'est plus sur
   la même machine que l'application.
2. **Le préfixe cPanel est obligatoire**, sur l'utilisateur *et* sur le nom de
   base : `abcd1234_monapp`, `abcd1234_mabase`. Copier-coller depuis cPanel ; un
   nom retapé de mémoire sans son préfixe est la panne la plus courante.
3. **Format strict** : ni guillemets, ni espace autour du `=`, ni commentaire en
   fin de ligne. `DB_PORT=3306 # port` donne la valeur `"3306 # port"`.

### 5.3 Tester la connexion hors de l'application

Isoler le problème avant de soupçonner le code :

```bash
cd /opt/kouttab
set -a; . ./.env; set +a
docker compose run --rm api python -c "
import pymysql, os
c = pymysql.connect(host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']),
                    user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                    database=os.environ['DB_NAME'], charset='utf8mb4')
cur = c.cursor(); cur.execute('SELECT VERSION()'); print('OK', cur.fetchone())
"
```

Erreurs typiques : `(1130, ... is not allowed to connect)` → IP non autorisée
(§5.1) ; `(1045, Access denied)` → préfixe cPanel manquant ou mot de passe ;
`(2003, Can't connect)` → hôte erroné.

### 5.4 Chiffrement — la décision à prendre

La liaison MySQL n'est pas chiffrée par défaut, et cette base transporte des
**RIB**, classés « TRÈS sensible » dans le CLAUDE.md. Vérifier si le serveur
accepte TLS :

```bash
docker compose run --rm api python -c "
import pymysql, os
c = pymysql.connect(host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']),
                    user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                    database=os.environ['DB_NAME'], ssl={'ssl': {}})
cur = c.cursor(); cur.execute(\"SHOW STATUS LIKE 'Ssl_cipher'\"); print(cur.fetchone())
"
```

- **Un chiffrement s'affiche** → ajouter au `.env` la ligne
  `DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/BASE?charset=utf8mb4&ssl=true`
  (elle prend le pas sur les `DB_*`). Rien d'autre à faire.
- **Vide, ou la connexion échoue** → activer le tunnel SSH :

```bash
ssh-keygen -t ed25519 -C "tunnel@kouttab" -f /opt/kouttab/secrets/id_tunnel -N ""
chmod 600 /opt/kouttab/secrets/id_tunnel
cat /opt/kouttab/secrets/id_tunnel.pub        # à importer dans cPanel → Accès SSH
ssh-keyscan -p 22 <hôte_ssh_o2switch> > /opt/kouttab/secrets/known_hosts

# puis DB_HOST=db-tunnel et DB_PORT=3306 dans le .env
docker compose --profile tunnel up -d db-tunnel
docker compose logs -f db-tunnel
```

Le tunnel n'est **pas** activé par défaut : la connexion directe est le montage
éprouvé ailleurs dans l'association, et une pièce en moins est une panne en
moins.

## 6. Renseigner le `.env`

```bash
nano /opt/kouttab/.env      # modèle : .env.deploy.example
chmod 600 /opt/kouttab/.env
```

Points de vigilance :

- `JWT_SECRET_KEY` : générer avec
  `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`.
  L'application **refuse de démarrer** en production avec la valeur par défaut.
- `CORS_ORIGINS` n'accepte que du `https://` en production (même garde-fou).
- `DB_HOST=db-tunnel` et `DB_PORT=3306` : c'est le tunnel, pas O2Switch en direct.
- `GHCR_OWNER` : ton compte GitHub, **en minuscules**.

## 7. Secrets GitHub

`Settings → Secrets and variables → Actions` :

| Nom | Type | Valeur |
|---|---|---|
| `VPS_HOST` | secret | `85.215.168.239` |
| `VPS_USER` | secret | `deploy` |
| `VPS_SSH_KEY` | secret | contenu de `~/.ssh/kouttab_deploy` (clé **privée**) |
| `VPS_KNOWN_HOSTS` | secret | `ssh-keyscan 85.215.168.239` |
| `SITE_DOMAIN` | variable | `stock.lekouttab.fr` |

Si le dépôt est privé, autoriser le VPS à tirer les images :
`docker login ghcr.io -u <compte> -p <token_avec_read:packages>`.

## 8. Premier déploiement

Le schéma existe déjà en base : il ne faut **pas** rejouer les migrations
initiales, seulement déclarer où l'on en est.

```bash
cd /opt/projets/kouttab-stock
docker compose pull

# 1. Sauvegarder la base depuis cPanel AVANT toute migration.
# 2. Constater l'état réel plutôt que de le supposer :
docker compose run --rm api alembic current
#    - une révision s'affiche  -> passer directement à `upgrade head` ;
#    - rien ne s'affiche mais les tables existent (schéma hérité du legacy
#      Streamlit) -> marquer la révision déjà en place AVANT d'appliquer :
docker compose run --rm api alembic stamp <revision_deja_appliquee>
# 3. Appliquer le reste.
docker compose run --rm api alembic upgrade head

docker compose up -d
docker compose ps          # les 3 services doivent être "running"
```

> **Ne jamais lancer `alembic upgrade head` sans avoir regardé `alembic current`.**
> Rejouer une migration initiale sur un schéma déjà en place échoue au mieux,
> et laisse la base à moitié migrée au pire.

## 9. Routage et TLS

Le certificat est demandé par le Caddy **du socle**, dès qu'il lit notre
fragment. Le DNS doit donc pointer sur le VPS **avant** le rechargement.

```bash
# 1. Enregistrement A : stock.lekouttab.fr -> 85.215.168.239
#    (baisser le TTL à 300 s la veille pour pouvoir revenir en arrière vite)
nslookup stock.lekouttab.fr        # doit renvoyer 85.215.168.239

# 2. Déposer notre fragment — un fichier À NOUS, on ne touche pas aux autres
cp /opt/projets/kouttab-stock/deploy/site.caddy \
   /opt/infra/sites/kouttab-stock.caddy

# 3. Recharger À CHAUD
cd /opt/infra
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose exec caddy caddy reload   --config /etc/caddy/Caddyfile

# 4. Vérifier l'obtention du certificat
docker compose logs --tail 50 caddy | grep -i certificate
```

> ⚠️ **`docker compose restart caddy` est interdit pour cela** : un redémarrage
> coupe brièvement *tous* les sites de la machine. `reload` recharge à chaud,
> sans interruption.
>
> ⚠️ `caddy validate` vérifie la syntaxe, **pas** que le routage fonctionne.
> La seule preuve est une requête réelle (§10).
>
> Let's Encrypt limite les échecs de validation par domaine et par heure : un
> DNS qui ne pointe pas encore sur le VPS bloque le domaine pour un moment.

## 10. Vérifications de bout en bout

```bash
curl -fsS https://stock.lekouttab.fr/api/v1/health
curl -sI https://stock.lekouttab.fr | grep -i strict-transport
```

Puis, dans le navigateur : connexion, une page de stock, dépôt d'une note de
frais avec justificatif (vérifie tunnel + upload + PDF + file d'envoi), et
`docker compose logs outbox-worker` pour confirmer le traitement de la file.

## 11. Sauvegardes — le point à ne pas oublier

La base reste sauvegardée par O2Switch. **Les fichiers, non.** Les volumes
`uploads` (justificatifs) et `outbox` vivent désormais sur le VPS et
disparaîtraient avec lui.

```bash
# À placer dans un cron quotidien, avec copie hors du VPS.
docker run --rm -v kouttab-stock_uploads:/data:ro -v /opt/kouttab/backups:/out \
  alpine tar czf /out/uploads-$(date +%F).tar.gz -C /data .
```

## 12. Retour arrière

Chaque déploiement épingle un tag d'image et conserve le `.env` précédent.

```bash
cd /opt/kouttab
cp .env.precedent .env         # restaure l'IMAGE_TAG d'avant
docker compose up -d
```

Une migration Alembic, elle, ne se défait pas toute seule : si le déploiement a
migré le schéma, restaurer aussi la sauvegarde de base prise à l'étape 8.
C'est la raison pour laquelle cette sauvegarde est obligatoire.

## 13. Exploitation courante

```bash
docker compose ps                     # état des services
docker compose logs -f api            # journaux de l'API
docker compose logs --tail=50 caddy   # TLS, accès
docker compose restart api            # redémarrage ciblé
docker compose exec api python scripts/process_outbound_emails.py   # forcer la file
```
