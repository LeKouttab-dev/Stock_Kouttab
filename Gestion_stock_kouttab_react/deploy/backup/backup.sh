#!/bin/sh
# ---------------------------------------------------------------------------
# Sauvegarde des fichiers déposés par les bénévoles.
#
# Ce que couvre ce script, et pourquoi il existe : la base MySQL reste chez
# O2Switch, qui la sauvegarde. Les justificatifs, eux, ne sont PAS en base — la
# table ne stocke qu'un chemin (`FichiersNotesDeFrais.chemin_fichier`) — et
# vivent dans des volumes Docker sur le VPS. Perdre le VPS, c'était perdre
# toutes les pièces comptables sans qu'aucune sauvegarde ne les rattrape.
#
# La copie part chez O2Switch : une archive restée sur le VPS ne protège que
# des suppressions accidentelles, pas de la perte de la machine, qui est
# précisément le risque à couvrir.
#
# Toute la rotation distante se fait à partir des NOMS de fichiers, qui portent
# leur date au format ISO. Aucune dépendance à un shell distant ni au parsing
# d'un listing : l'accès distant peut donc rester au minimum de privilèges.
#
# DEUX PROTOCOLES, choisis par `BACKUP_PROTOCOLE` :
#
#   sftp  — le meilleur : clé SSH, révocable, restreignable au seul transfert.
#   ftps  — FTP chiffré par TLS, pour les hébergements qui n'ouvrent pas SSH.
#           C'est le cas d'O2Switch sur ce compte : le port 22 est fermé, le 21
#           répond. Le FTP en clair, lui, n'est jamais utilisé — ces archives
#           contiennent des noms, des montants et des pièces comptables.
#
# En FTPS, un mot de passe remplace la clé. Il vit dans le `.env` (600) et doit
# appartenir à un compte FTP **dédié, cantonné au dossier des sauvegardes** :
# s'il fuite, il n'ouvre que cela.
# ---------------------------------------------------------------------------
set -eu

PREFIXE="${BACKUP_PREFIX:-kouttab-fichiers}"
# Chemins surchargeables : les valeurs par défaut sont celles des montages du
# conteneur, et les variables permettent d'exercer le script hors de Docker.
SOURCE_DIR="${BACKUP_SOURCE_DIR:-/data}"
SOURCE_UPLOADS="$SOURCE_DIR/uploads"
LOCAL_DIR="${BACKUP_LOCAL_DIR:-/backups}"
CLE="${BACKUP_SSH_KEY:-/etc/backup/backup_ssh_key}"
KNOWN_HOSTS="${BACKUP_KNOWN_HOSTS:-/etc/backup/backup_known_hosts}"

HOTE="${BACKUP_SFTP_HOST:-}"
PORT="${BACKUP_SFTP_PORT:-22}"
UTILISATEUR="${BACKUP_SFTP_USER:-}"
DISTANT="${BACKUP_SFTP_DIR:-sauvegardes/kouttab-stock}"

GARDE_LOCAL="${BACKUP_KEEP_LOCAL_DAYS:-7}"
GARDE_DISTANT="${BACKUP_KEEP_REMOTE_DAYS:-30}"
HEURE="${BACKUP_HOUR:-3}"

journal() {
	echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

erreur() {
	journal "ERREUR : $*" >&2
}

# -- Envoi ------------------------------------------------------------------

preparer_cle() {
	# La clé est montée en lecture seule depuis le VPS. Si elle y est lisible
	# par tous, `ssh` refuse catégoriquement de s'en servir — et le montage
	# étant en lecture seule, on ne peut pas corriger ses droits en place.
	# D'où la copie, dont on maîtrise les permissions.
	if [ ! -f "$CLE" ]; then
		erreur "clé de sauvegarde absente ($CLE) — voir DEPLOIEMENT-VPS.md §11"
		return 1
	fi
	if [ ! -f "$KNOWN_HOSTS" ]; then
		erreur "empreinte du serveur absente ($KNOWN_HOSTS) — voir DEPLOIEMENT-VPS.md §11"
		return 1
	fi
	cp "$CLE" /tmp/cle_sauvegarde
	chmod 600 /tmp/cle_sauvegarde
	CLE=/tmp/cle_sauvegarde
}

sftp_lot() {
	# `-b -` : les commandes SFTP arrivent par l'entrée standard.
	# StrictHostKeyChecking à `yes` : sans empreinte connue d'avance, on
	# livrerait les justificatifs de l'association à qui répondrait à cette
	# adresse.
	sftp -b - \
		-i "$CLE" \
		-P "$PORT" \
		-o "UserKnownHostsFile=$KNOWN_HOSTS" \
		-o StrictHostKeyChecking=yes \
		-o BatchMode=yes \
		-o ConnectTimeout=30 \
		"${UTILISATEUR}@${HOTE}"
}

creations_repertoires() {
	# `mkdir` en SFTP ne crée pas les parents : sur un chemin comme
	# `sauvegardes/kouttab-stock`, un seul `mkdir` échoue tant que
	# `sauvegardes` n'existe pas. On émet donc un `mkdir` par niveau, préfixé
	# de `-` pour que les niveaux déjà présents n'interrompent pas le lot.
	chemin=""
	echo "$DISTANT" | tr '/' '\n' | while read -r segment; do
		[ -z "$segment" ] && continue
		chemin="${chemin:+$chemin/}$segment"
		echo "-mkdir $chemin"
	done
}

envoyer() {
	archive="$1"
	nom=$(basename "$archive")

	# Le dépôt se fait sous un nom temporaire, renommé une fois complet : une
	# coupure réseau en cours de transfert laisserait sinon une archive
	# tronquée portant un nom parfaitement normal, qu'on croirait valide le
	# jour où on en a besoin.
	{
		creations_repertoires
		echo "put $archive $DISTANT/$nom.partiel"
		echo "-rm $DISTANT/$nom"
		echo "rename $DISTANT/$nom.partiel $DISTANT/$nom"
		echo "bye"
	} | sftp_lot
}

verifier_distant() {
	nom="$1"
	taille_locale="$2"

	# `ls -l` distant, dont on ne garde que la taille : la sauvegarde n'est
	# déclarée réussie que si l'octet compte y est. Un `put` qui rend la main
	# sans erreur après un disque distant plein n'est pas une garantie.
	ligne=$(printf 'ls -l %s/%s\nbye\n' "$DISTANT" "$nom" | sftp_lot 2>/dev/null | grep -- "$nom" | head -n 1 || true)
	if [ -z "$ligne" ]; then
		erreur "archive introuvable chez O2Switch après envoi : $nom"
		return 1
	fi

	taille_distante=$(echo "$ligne" | awk '{ print $5 }')
	if [ "$taille_distante" != "$taille_locale" ]; then
		erreur "taille incohérente pour $nom (locale $taille_locale, distante $taille_distante)"
		return 1
	fi

	journal "vérifié chez O2Switch : $nom ($taille_distante octets)"
}

# -- Rotation ---------------------------------------------------------------

purger_distant() {
	# On ne demande pas au serveur quels fichiers sont vieux : on calcule les
	# noms des jours à supprimer et on les efface. Un `rm` sur un fichier
	# absent renvoie une erreur sans conséquence, d'où le `-` de `-rm`.
	i=$((GARDE_DISTANT + 1))
	fin=$((GARDE_DISTANT + 30))
	lot=""
	while [ "$i" -le "$fin" ]; do
		jour=$(date -d "$i days ago" +%F)
		lot="${lot}-rm $DISTANT/$PREFIXE-$jour.tar.gz
"
		i=$((i + 1))
	done
	printf '%sbye\n' "$lot" | sftp_lot >/dev/null 2>&1 || true
	journal "rotation distante : sauvegardes de plus de $GARDE_DISTANT jours effacées"
}

purger_local() {
	find "$LOCAL_DIR" -name "$PREFIXE-*.tar.gz" -type f -mtime "+$GARDE_LOCAL" -delete
	journal "rotation locale : archives de plus de $GARDE_LOCAL jours effacées"
}

# -- Sauvegarde -------------------------------------------------------------

sauvegarder() {
	jour=$(date +%F)
	nom="$PREFIXE-$jour.tar.gz"
	archive="$LOCAL_DIR/$nom"

	if [ ! -d "$SOURCE_UPLOADS" ]; then
		erreur "volume des justificatifs absent ($SOURCE_UPLOADS) — rien à sauvegarder"
		return 1
	fi

	mkdir -p "$LOCAL_DIR"
	journal "archivage en cours vers $archive"

	# Écriture sous un nom temporaire pour la même raison qu'à l'envoi : une
	# archive interrompue ne doit jamais porter le nom du jour.
	if ! tar czf "$archive.partiel" -C "$SOURCE_DIR" uploads outbox 2>/dev/null; then
		# `outbox` peut manquer sur une installation neuve : on retente sans.
		tar czf "$archive.partiel" -C "$SOURCE_DIR" uploads
	fi
	mv "$archive.partiel" "$archive"

	taille=$(stat -c %s "$archive")
	journal "archive prête : $nom ($taille octets)"

	# L'archive locale est faite avant tout contrôle d'accès distant : même
	# sans destination configurée, elle protège d'une suppression
	# accidentelle. L'échec porte sur la copie hors-site, pas sur l'archive.
	if [ -z "$HOTE" ] || [ -z "$UTILISATEUR" ]; then
		erreur "BACKUP_SFTP_HOST / BACKUP_SFTP_USER non renseignés — l'archive reste sur le VPS, sans copie hors-site"
		purger_local
		return 1
	fi
	if ! preparer_cle; then
		purger_local
		return 1
	fi

	envoyer "$archive"
	verifier_distant "$nom" "$taille"

	purger_distant
	purger_local
	journal "sauvegarde du $jour terminée"
}

# -- Ordonnancement ---------------------------------------------------------

attendre_heure() {
	maintenant=$(date +%s)
	cible=$(date -d "today ${HEURE}:00:00" +%s)
	[ "$cible" -le "$maintenant" ] && cible=$(date -d "tomorrow ${HEURE}:00:00" +%s)
	delai=$((cible - maintenant))
	journal "prochaine sauvegarde dans $((delai / 3600)) h $(((delai % 3600) / 60)) min"
	sleep "$delai"
}

case "${1:-boucle}" in
maintenant)
	# Sauvegarde immédiate : sert à valider la configuration au moment de
	# l'installation, sans attendre 3 h du matin.
	sauvegarder
	;;
boucle)
	if [ "${BACKUP_ENABLED:-true}" != "true" ]; then
		journal "BACKUP_ENABLED=false — service en veille"
		while true; do sleep 3600; done
	fi
	journal "service de sauvegarde démarré (cible : ${HEURE}h, destination : ${UTILISATEUR:-?}@${HOTE:-?}:$DISTANT)"
	while true; do
		attendre_heure
		# Un échec ne doit pas tuer la boucle : le lendemain a toutes les
		# chances de réussir, et un conteneur mort ne sauvegarde plus rien.
		sauvegarder || erreur "sauvegarde échouée — nouvelle tentative demain"
	done
	;;
*)
	erreur "usage : backup.sh [boucle|maintenant]"
	exit 64
	;;
esac
