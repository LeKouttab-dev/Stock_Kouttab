# Kouttab Stock — Backend (FastAPI)

API REST pour la gestion des stocks, notes de frais et factures de l'association
Le Kouttab. Stack : FastAPI + SQLAlchemy 2 + MySQL (PyMySQL) + JWT.

## Demarrage local

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# ou : source .venv/bin/activate # Linux / macOS

pip install -r requirements.txt
copy .env.example .env          # puis remplir DB_PASSWORD, JWT_SECRET_KEY, SMTP_*

uvicorn app.main:app --reload --port 8000
```

Documentation interactive :
- Swagger UI : http://localhost:8000/docs
- ReDoc      : http://localhost:8000/redoc

## Tests

```bash
# Installer les deps de dev (pytest, pytest-cov, freezegun, ...)
pip install -r requirements-dev.txt

# Lancer toute la suite
pytest -q

# Couverture (terminal + rapport HTML dans htmlcov/)
pytest --cov=app --cov-report=term-missing --cov-report=html

# Ne lancer que les tests unitaires (rapides, pas d'HTTP)
pytest tests/unit -q

# Ne lancer que les tests d'integration (plus lents, frappent l'API)
pytest tests/integration -q
```

Les tests utilisent une base SQLite en memoire (override `get_db`).
Structure des tests :
- `tests/unit/`        — logique CRUD/securite pure
- `tests/integration/` — endpoints FastAPI via `TestClient`
- `tests/conftest.py`  — fixtures partagees : utilisateurs par role,
  `auth_headers(user)`, `client_authenticated_as(user)`, capture des emails.

## Migrations Alembic

Le schema MySQL existe deja sur O2Switch. Pour les nouveaux deploiements :

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head

# Sur l'environnement de prod existant (schema deja present) :
alembic stamp head
```

## Structure

```
app/
├── api/v1/endpoints/   # routes FastAPI
├── core/               # config, securite, logger, exceptions
├── crud/               # logique metier pure (sans FastAPI)
├── db/                 # SQLAlchemy : engine + Base + models
├── schemas/            # Pydantic v2 (in/out)
├── services/           # email, fichiers, import CSV
└── utils/
```

## Deploiement O2Switch (Passenger)

1. Build du front + upload de `dist/` vers `/www/stock.lekouttab.fr/`.
2. Upload du dossier `backend/` vers `/www/stock.lekouttab.fr/backend/`.
3. cPanel -> Setup Python App :
   - Python 3.11
   - Application root : `/www/stock.lekouttab.fr/backend`
   - Startup file : `passenger_wsgi.py`
4. SSH : `pip install -r backend/requirements.txt`.
5. `alembic stamp head` (la base existe deja).
6. Restart Passenger : `touch tmp/restart.txt`.

## Variables d'environnement

Voir `.env.example`. Variables critiques :
- `JWT_SECRET_KEY` (generer via `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- `DB_*`
- `SMTP_*` (sinon les emails sont silencieusement ignores avec un log)
- `CORS_ORIGINS`

## Roles & permissions

Voir `../CLAUDE.md` section 5. La logique est dans `app/api/deps.py::require_roles`.
