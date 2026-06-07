"""Extracción con Anthropic Claude — lectura nativa de PDF vectorial."""
from __future__ import annotations

import base64
import logging

import anthropic

from app.config import settings
from app.models.label import ArtworkLabel, InciLabel, clean_artwork, clean_inci, parse_json
from app.models.schemas import ValidationReport
from app.services.comparator import build_report
from app.services.metrics import record
from app.services.prompts import PROMPT_ARTWORK, PROMPT_PACKAGE, build_narrative_prompt

logger = logging.getLogger(__name__)


# Instancia el cliente Anthropic con la API key de configuración.
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# Envía el PDF base64 a Claude y extrae la etiqueta del artwork.
def _extract_artwork(pdf_bytes: bytes) -> ArtworkLabel:
    response = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode(),
                    },
                },
                {"type": "text", "text": PROMPT_ARTWORK},
            ],
        }],
    )
    record("claude", settings.anthropic_model, "artwork",
           response.usage.input_tokens, response.usage.output_tokens)
    return clean_artwork(parse_json(response.content[0].text))


# Envía las fotos del embalaje y extrae la lista INCI del packaging físico.
def _extract_package(photo_bytes_list: list[bytes]) -> InciLabel:
    content: list = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(photo).decode(),
            },
        }
        for photo in photo_bytes_list
    ]
    content.append({"type": "text", "text": PROMPT_PACKAGE})

    response = _client().messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )
    record("claude", settings.anthropic_model, "package",
           response.usage.input_tokens, response.usage.output_tokens)
    return clean_inci(parse_json(response.content[0].text))


# Genera una valoración global en español con Haiku (modelo ligero).
def _generate_narrative(report: ValidationReport) -> str:
    msg = _client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": build_narrative_prompt(report)}],
    )
    record("claude", "claude-haiku-4-5-20251001", "narrative",
           msg.usage.input_tokens, msg.usage.output_tokens)
    return msg.content[0].text.strip()


# Punto de entrada público: extrae artwork y package, devuelve el informe.
def compare(pdf_bytes: bytes, photo_bytes_list: list[bytes]) -> ValidationReport:
    artwork = _extract_artwork(pdf_bytes)
    package = _extract_package(photo_bytes_list)
    logger.info("Claude — artwork: %d ingredientes, package: %d ingredientes",
                len(artwork.ingredients), len(package.ingredients))
    report = build_report(artwork, package)
    try:
        report.narrative = _generate_narrative(report)
    except Exception as exc:
        logger.warning("Narrative generation failed: %s", exc)
    return report
