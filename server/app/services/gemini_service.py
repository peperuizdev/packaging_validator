"""Extracción con Google Gemini — artwork rasterizado, fotos nativas.

El PDF del artwork se convierte a imágenes antes de enviarlo. En modo lectura
nativa de PDF, Gemini aplica conocimiento semántico y fusiona entradas INCI que
reconoce como compuestos o variantes del mismo colorante. El OCR visual sobre
imágenes es literal y produce resultados equivalentes a Claude y GPT-4o.
"""
from __future__ import annotations

import logging

import fitz  # PyMuPDF
from google import genai
from google.genai import types as gentypes

from app.config import settings
from app.models.label import ArtworkLabel, InciLabel, clean_artwork, clean_inci, parse_json
from app.models.schemas import ValidationReport
from app.services.comparator import build_report
from app.services.metrics import record
from app.services.prompts import PROMPT_ARTWORK, PROMPT_PACKAGE, build_narrative_prompt

logger = logging.getLogger(__name__)


# Cliente singleton — evita que el SDK cierre la sesión HTTP entre llamadas.
_gemini_client: genai.Client | None = None

def _client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _mime_type(data: bytes) -> str:
    if data[:3] == b'\xff\xd8\xff':
        return "image/jpeg"
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"


# Convierte cada página del PDF en PNG lossless para OCR visual.
def _rasterize_pdf(pdf_bytes: bytes, dpi: int = 200) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)
    images = [page.get_pixmap(matrix=matrix, alpha=False).tobytes("png") for page in doc]
    doc.close()
    return images


# Llama a Gemini con las partes dadas, registra uso y devuelve el texto de la respuesta.
def _generate(client: genai.Client, parts: list, model: str, phase: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=gentypes.Content(role="user", parts=parts),
        config=gentypes.GenerateContentConfig(
            max_output_tokens=4096,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    candidate = response.candidates[0]
    if candidate.finish_reason and candidate.finish_reason.name == "RECITATION":
        raise RuntimeError("Gemini bloqueó la respuesta por RECITATION. Prueba con Claude.")
    raw = response.text or ""
    if not raw.strip():
        raise RuntimeError("Gemini devolvió una respuesta vacía.")
    usage = response.usage_metadata
    record("gemini", model, phase,  # type: ignore[arg-type]
           getattr(usage, "prompt_token_count", 0) or 0,
           getattr(usage, "candidates_token_count", 0) or 0)
    logger.debug("gemini %s raw:\n%s", phase, raw)
    return raw


# Rasteriza el PDF y extrae la etiqueta del artwork mediante OCR visual.
def _extract_artwork(pdf_bytes: bytes) -> ArtworkLabel:
    parts: list = [
        gentypes.Part(inline_data=gentypes.Blob(mime_type="image/png", data=img))
        for img in _rasterize_pdf(pdf_bytes)
    ]
    parts.append(gentypes.Part(text=PROMPT_ARTWORK))
    return clean_artwork(parse_json(_generate(_client(), parts, settings.gemini_model, "artwork")))


# Envía las fotos del embalaje y extrae la lista INCI del packaging físico.
def _extract_package(photo_bytes_list: list[bytes]) -> InciLabel:
    parts: list = [
        gentypes.Part(inline_data=gentypes.Blob(mime_type=_mime_type(photo), data=photo))
        for photo in photo_bytes_list
    ]
    parts.append(gentypes.Part(text=PROMPT_PACKAGE))
    return clean_inci(parse_json(_generate(_client(), parts, settings.gemini_model, "package")))


# Genera una valoración global en español con Gemini Flash Lite (modelo ligero).
def _generate_narrative(report: ValidationReport) -> str:
    narrative_model = "gemini-2.5-flash-lite"
    response = _client().models.generate_content(
        model=narrative_model,
        contents=gentypes.Content(
            role="user",
            parts=[gentypes.Part(text=build_narrative_prompt(report))],
        ),
        config=gentypes.GenerateContentConfig(max_output_tokens=200, temperature=0.3),
    )
    usage = response.usage_metadata
    record("gemini", narrative_model, "narrative",
           getattr(usage, "prompt_token_count", 0) or 0,
           getattr(usage, "candidates_token_count", 0) or 0)
    logger.debug("gemini narrative raw:\n%s", response.text)
    return (response.text or "").strip()


# Punto de entrada público: extrae artwork y package, devuelve el informe.
def compare(pdf_bytes: bytes, photo_bytes_list: list[bytes]) -> ValidationReport:
    artwork = _extract_artwork(pdf_bytes)
    package = _extract_package(photo_bytes_list)
    logger.info("Gemini — artwork: %d ingredientes, package: %d ingredientes",
                len(artwork.ingredients), len(package.ingredients))
    report = build_report(artwork, package)
    try:
        report.narrative = _generate_narrative(report)
    except Exception as exc:
        logger.warning("Narrative generation failed: %s", exc)
    return report
