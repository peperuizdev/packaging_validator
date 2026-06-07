"""POST /api/validate — recibe artwork PDF + fotos y devuelve ValidationReport."""
from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.models.schemas import ValidationReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["validation"])

Provider = Literal["claude", "gemini", "openai"]

# Registro de proveedores: añadir uno nuevo = una línea aquí + un módulo nuevo.
_PROVIDER_MODULES: dict[str, str] = {
    "claude": "app.services.claude_service",
    "gemini": "app.services.gemini_service",
    "openai": "app.services.openai_service",
}


# Importa el módulo del proveedor de forma diferida para no cargar todos los SDK en startup.
def _get_compare(provider: Provider):
    return importlib.import_module(_PROVIDER_MODULES[provider]).compare


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics() -> dict:
    from app.services.metrics import get_summary
    return get_summary()


@router.post("/validate", response_model=ValidationReport)
async def validate(
    artwork:  Annotated[UploadFile, File(description="Artwork PDF")],
    photos:   Annotated[list[UploadFile], File(description="1 o 2 fotos del embalaje")],
    provider: Provider = Query("claude", description="Proveedor LLM: claude | gemini | openai"),
) -> ValidationReport:
    if not artwork.filename or not artwork.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="El artwork debe ser un archivo PDF.")
    if not (1 <= len(photos) <= 2):
        raise HTTPException(status_code=422, detail="Se requieren entre 1 y 2 fotos del embalaje.")

    artwork_bytes    = await artwork.read()
    photo_bytes_list = [await p.read() for p in photos]
    compare          = _get_compare(provider)

    try:
        return await asyncio.to_thread(compare, artwork_bytes, photo_bytes_list)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Validation failed with provider=%s", provider)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")
