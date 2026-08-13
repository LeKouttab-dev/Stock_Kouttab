"""FastAPI application entry-point."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import ERROR_MESSAGES, ErrorCode
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.core.rate_limit import limiter
from app.crud import expense_category as category_crud
from app.crud import pole as pole_crud
from app.db.session import SessionLocal


logger = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.outbox_path.mkdir(parents=True, exist_ok=True)

    # Le referentiel des poles est seede par la migration Alembic, mais les
    # tests et les environnements de developpement montent le schema via
    # create_all() sans jouer les migrations : ils auraient une table vide.
    db = SessionLocal()
    try:
        pole_crud.ensure_default_poles(db)
        category_crud.ensure_default_categories(db)
    except Exception as exc:  # noqa: BLE001 — ne jamais empecher le demarrage
        logger.warning("Initialisation des poles par defaut ignoree : %s", exc)
    finally:
        db.close()

    # Un courriel coupe ne se voit nulle part tant que personne ne depose de
    # piece : la production a tourne trois semaines ainsi. Le dire au demarrage
    # ne suffit pas — l'ecran des envois le montre aussi — mais c'est la
    # premiere ligne que lit celui qui diagnostique.
    if not settings.email_enabled:
        logger.warning(
            "EMAIL_ENABLED=false — AUCUN courriel ne partira : ni les pieces au "
            "comptable, ni les changements de statut, ni les relances. "
            "Corriger le .env puis redemarrer si ce n'est pas voulu."
        )
    elif not (settings.smtp_host and settings.smtp_user):
        logger.warning(
            "SMTP_HOST ou SMTP_USER manquant — les envois echoueront tous."
        )

    logger.info("Kouttab Stock API demarre (env=%s)", settings.app_env)
    yield
    logger.info("Kouttab Stock API arrete.")


# La documentation interactive decrit toute la surface d'API (endpoints admin,
# schemas, codes d'erreur). On la reserve aux environnements non-production.
_docs_enabled = not settings.is_production

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (slowapi). We override the default 429 response so it follows the
# standard ``{code, message, extras}`` envelope and exposes the ``RATE_7001`` code.
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:  # noqa: ARG001
    code = ErrorCode.RATE_LIMIT_EXCEEDED
    if request.url.path.endswith("/auth/login"):
        code = ErrorCode.LOGIN_RATE_LIMITED
    _, message = ERROR_MESSAGES[code]
    return JSONResponse(
        status_code=429,
        content={
            "code": code.value,
            "message": message,
            "extras": {"limit": str(exc.detail) if exc.detail else None},
            "error": code.value,
            "details": {"limit": str(exc.detail) if exc.detail else None},
        },
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
# Keep the slowapi default handler ref to avoid an unused-import lint warning.
_ = _rate_limit_exceeded_handler
app.add_middleware(SlowAPIMiddleware)


# Taille maximale du corps de requete. ``MAX_REQUEST_MB`` etait declare dans la
# configuration mais n'etait lu nulle part : la limite n'existait pas.
@app.middleware("http")
async def _limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_request_mb * 1024 * 1024:
                _, message = ERROR_MESSAGES[ErrorCode.FILE_TOO_LARGE]
                return JSONResponse(
                    status_code=413,
                    content={
                        "code": ErrorCode.FILE_TOO_LARGE.value,
                        "message": message,
                        "extras": {"max_mb": settings.max_request_mb},
                    },
                )
        except ValueError:
            pass
    return await call_next(request)


# En-tetes de securite. Ils completent ceux du .htaccess : en developpement
# (uvicorn seul) Apache n'est pas dans la boucle, et en production une reponse
# servie directement par Passenger ne passe pas toujours par les regles Apache.
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(self)"
    )
    # L'API ne rend que du JSON : aucune ressource n'a besoin d'etre chargee.
    # Exception pour Swagger UI / ReDoc, qui chargent leurs assets depuis un CDN
    # et seraient des pages blanches sous cette politique (dev uniquement).
    if request.url.path not in ("/docs", "/redoc", "/docs/oauth2-redirect"):
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


# Request timing log
@app.middleware("http")
async def _log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Process-Time-ms"] = f"{duration_ms:.1f}"
    return response


# Custom exception handlers
register_exception_handlers(app)


# v1 router (prefix /api/v1)
app.include_router(api_router, prefix="/api/v1")


# Health endpoint (used by O2Switch / UptimeRobot)
@app.get("/health", tags=["meta"])
@app.get("/api/v1/health", tags=["meta"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.app_version})


# Root
@app.get("/", tags=["meta"])
def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }
    )
