"""Extracción con OpenAI GPT-4o — Responses API con PDF nativo e imágenes."""
from __future__ import annotations

import base64
import logging

from openai import OpenAI

from app.config import settings
from app.models.label import ArtworkLabel, InciLabel, clean_artwork, clean_inci, parse_json
from app.models.schemas import ValidationReport
from app.services.comparator import build_report
from app.services.metrics import record
from app.services.prompts import PROMPT_ARTWORK, PROMPT_PACKAGE, build_narrative_prompt

logger = logging.getLogger(__name__)


# Instancia el cliente OpenAI con la API key de configuración.
def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


# Envía el PDF como data URL a la Responses API y extrae la etiqueta del artwork.
def _extract_artwork(pdf_bytes: bytes) -> ArtworkLabel:
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = _client().responses.create(
        model=settings.openai_model,
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "filename": "artwork.pdf",
                    "file_data": f"data:application/pdf;base64,{b64}",
                },
                {"type": "input_text", "text": PROMPT_ARTWORK},
            ],
        }],
        text={"format": {"type": "json_object"}},
    )
    record("openai", settings.openai_model, "artwork",
           response.usage.input_tokens, response.usage.output_tokens)
    return clean_artwork(parse_json(response.output_text))


# Envía las fotos como imágenes de alta resolución y extrae la lista INCI.
def _extract_package(photo_bytes_list: list[bytes]) -> InciLabel:
    content: list = [
        {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{base64.standard_b64encode(photo).decode()}",
            "detail": "high",
        }
        for photo in photo_bytes_list
    ]
    content.append({"type": "input_text", "text": PROMPT_PACKAGE})

    response = _client().responses.create(
        model=settings.openai_model,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_object"}},
    )
    record("openai", settings.openai_model, "package",
           response.usage.input_tokens, response.usage.output_tokens)
    return clean_inci(parse_json(response.output_text))


# Genera una valoración global en español con gpt-4o-mini (modelo ligero).
def _generate_narrative(report: ValidationReport) -> str:
    resp = _client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": build_narrative_prompt(report)}],
        max_tokens=200,
        temperature=0.3,
    )
    record("openai", "gpt-4o-mini", "narrative",
           resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return (resp.choices[0].message.content or "").strip()


# Punto de entrada público: extrae artwork y package, devuelve el informe.
def compare(pdf_bytes: bytes, photo_bytes_list: list[bytes]) -> ValidationReport:
    artwork = _extract_artwork(pdf_bytes)
    package = _extract_package(photo_bytes_list)
    logger.info("OpenAI — artwork: %d ingredientes, package: %d ingredientes",
                len(artwork.ingredients), len(package.ingredients))
    report = build_report(artwork, package)
    try:
        report.narrative = _generate_narrative(report)
    except Exception as exc:
        logger.warning("Narrative generation failed: %s", exc)
    return report
