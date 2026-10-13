import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import auth, misc, periods, pots, recurring, transactions
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.migrate import upgrade_to_head
from app.db.session import get_engine
from app.services.bootstrap import ensure_defaults

log = logging.getLogger("finanzmanager")

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; font-src 'self' data:; manifest-src 'self'; "
    "worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def _error(status: int, code: str, message: str, details: object = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": details}}, status_code=status)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
        ]
        return _error(422, "validation_failed", "Bitte überprüfe deine Eingaben.", details)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        log.warning("integrity error: %s", exc.orig)
        return _error(409, "conflict", "Die Änderung widerspricht vorhandenen Daten.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = "Nicht gefunden" if exc.status_code == 404 else str(exc.detail)
        return _error(exc.status_code, "http_error", message)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return _error(500, "internal_error", "Ein unerwarteter Fehler ist aufgetreten.")


def _install_spa(app: FastAPI, dist: Path) -> None:
    """Serves the built PWA from the same origin as the API (no CORS needed)."""
    index = dist / "index.html"

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str) -> Response:
        if path.startswith("api/") or path == "api":
            return _error(404, "http_error", "Nicht gefunden")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            immutable = path.startswith("assets/")
            headers = {"Cache-Control": "public, max-age=31536000, immutable" if immutable else "no-cache"}
            return FileResponse(candidate, headers=headers)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app(settings: Settings | None = None, *, run_migrations: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if run_migrations:
            upgrade_to_head(settings.sqlalchemy_url)
        ensure_defaults(get_engine())
        yield

    app = FastAPI(
        title="FinanzManager",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.is_dev else None,
    )
    _install_error_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api/"):
            # Financial data must never land in a browser or service-worker cache.
            response.headers["Cache-Control"] = "no-store"
        return response

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (auth, periods, transactions, pots, recurring, misc):
        api.include_router(module.router)
    app.include_router(api)

    if settings.frontend_dist.joinpath("index.html").is_file():
        _install_spa(app, settings.frontend_dist)
    return app


app = create_app()
