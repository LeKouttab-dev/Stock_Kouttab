# ---------------------------------------------------------------------------
# Image de sauvegarde : archive les volumes de fichiers et les dépose chez
# O2Switch par SFTP.
#
# `coreutils` pour le `date -d "tomorrow 03:00"` de l'ordonnancement et du
# calcul de rotation : le `date` de BusyBox ne sait pas interpréter une date
# relative, et une rotation qui se trompe de jour efface des sauvegardes encore
# utiles.
# ---------------------------------------------------------------------------
FROM alpine:3.20

RUN apk add --no-cache openssh-client coreutils tar gzip

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# Sans HOME explicite, `ssh` cherche sa configuration dans /root et se plaint de
# ne pas trouver de répertoire inscriptible.
ENV HOME=/tmp

ENTRYPOINT ["/usr/local/bin/backup.sh"]
CMD ["boucle"]
