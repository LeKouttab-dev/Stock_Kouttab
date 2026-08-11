# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Étape 1 — dépendances
#
# Installées dans un venv isolé, copié tel quel dans l'image finale : les
# en-têtes de compilation et le cache pip ne suivent pas.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# build-essential n'est présent que dans cette étape : si une dépendance n'a
# pas de wheel pour cp312, elle se compile ici et le compilateur reste ici.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Étape 2 — image d'exécution
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Utilisateur non privilégié : une faille dans l'app ne donne pas root dans le
# conteneur. L'UID est figé pour que les volumes montés gardent le bon
# propriétaire d'un déploiement à l'autre.
RUN groupadd --gid 1001 kouttab \
    && useradd --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin kouttab

WORKDIR /app

COPY --from=deps /opt/venv /opt/venv
COPY --chown=kouttab:kouttab alembic.ini ./
COPY --chown=kouttab:kouttab alembic ./alembic
COPY --chown=kouttab:kouttab app ./app
COPY --chown=kouttab:kouttab scripts ./scripts

# Points de montage des volumes. Créés avec le bon propriétaire ici, sinon
# Docker les crée en root au premier démarrage et l'app ne peut plus y écrire.
RUN mkdir -p /app/uploads /app/outbox /app/logs \
    && chown -R kouttab:kouttab /app/uploads /app/outbox /app/logs

USER kouttab

EXPOSE 8000

# curl n'est pas installé (surface d'attaque inutile) : l'interpréteur suffit.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Un seul worker : la base est distante et le mutualisé O2Switch plafonne
# max_user_connections. Monter les workers multiplierait les pools de
# connexions et ferait tomber l'application sur un refus du serveur MySQL.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
