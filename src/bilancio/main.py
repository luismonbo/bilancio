from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bilancio.api.accounts import router as accounts_router
from bilancio.api.health import router as health_router
from bilancio.api.imports import router as imports_router
from bilancio.api.me import router as me_router
from bilancio.api.rules import router as rules_router
from bilancio.api.setup import router as setup_router
from bilancio.api.transactions import router as transactions_router
from bilancio.config import get_settings
from bilancio.observability.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.debug)

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Bilancio",
    version=settings.app_version,
    description="Personal finance tracker API",
)

# API routes
app.include_router(health_router)
app.include_router(setup_router)
app.include_router(me_router)
app.include_router(accounts_router)
app.include_router(imports_router)
app.include_router(transactions_router)
app.include_router(rules_router)


# Frontend — serve index.html at / and static assets at /static/*
@app.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
