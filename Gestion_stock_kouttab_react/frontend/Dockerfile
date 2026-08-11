# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Étape 1 — build Vite
#
# C'est l'étape qui consommait trop de mémoire sur le VPS : elle tourne
# désormais sur un runner GitHub, et le VPS ne verra jamais Node.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# `npm ci` avant la copie du source : tant que le lockfile ne bouge pas, cette
# couche est réutilisée et le build ne réinstalle pas les dépendances.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# ATTENTION : Vite remplace `import.meta.env.VITE_API_URL` à la compilation.
# L'URL de l'API est donc figée dans le bundle — c'est un argument de build,
# pas une variable d'environnement du conteneur. La changer impose de
# reconstruire l'image.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ---------------------------------------------------------------------------
# Étape 2 — service des fichiers statiques
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# nginx:alpine tourne déjà en non-root sur le port 8080 via l'utilisateur
# nginx pour les versions récentes ; on reste sur le port 80 interne, non
# publié : seul Caddy y accède, sur le réseau Docker.
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
