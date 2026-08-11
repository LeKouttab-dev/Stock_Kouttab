# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Tunnel SSH vers la base MySQL restée chez O2Switch.
#
# Pourquoi un conteneur plutôt qu'un service systemd sur l'hôte : un tunnel
# côté hôte doit écouter sur une adresse joignable depuis le réseau Docker,
# ce qui oblige à ouvrir un port sur la passerelle et à le refermer au pare-feu.
# Ici, le tunnel vit DANS le réseau Docker : l'API le joint par son nom de
# service (`db-tunnel`), et rien n'est exposé à l'extérieur du réseau.
#
# autossh relance la session dès qu'elle tombe — une coupure réseau chez
# O2Switch ne laisse donc pas l'application sans base jusqu'au prochain
# redémarrage.
# ---------------------------------------------------------------------------
FROM alpine:3.20

RUN apk add --no-cache autossh openssh-client \
    && adduser -D -u 1001 tunnel

USER tunnel
WORKDIR /home/tunnel

# AUTOSSH_GATETIME=0 : autossh reessaie meme si la toute premiere connexion
# echoue (au demarrage, le reseau Docker n'est pas toujours pret).
ENV AUTOSSH_GATETIME=0 \
    AUTOSSH_PORT=0

# -L 0.0.0.0:3306 : l'ecoute doit accepter les connexions des autres
# conteneurs du reseau, pas seulement de celui-ci.
# ExitOnForwardFailure : sans cette option, autossh croirait le tunnel etabli
# alors que la redirection a ete refusee, et l'API attendrait dans le vide.
CMD ["sh", "-c", "exec autossh -M 0 -N \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile=/home/tunnel/.ssh/known_hosts \
    -i /home/tunnel/.ssh/id_tunnel \
    -p ${O2SWITCH_SSH_PORT:-22} \
    -L 0.0.0.0:3306:${O2SWITCH_DB_HOST:-127.0.0.1}:3306 \
    ${O2SWITCH_SSH_USER}@${O2SWITCH_SSH_HOST}"]
