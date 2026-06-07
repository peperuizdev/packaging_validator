"""Registro en memoria de uso de tokens y coste por proveedor.

Precios en USD por millón de tokens (fuente: páginas de precios oficiales, junio 2026).
Costes devueltos en EUR (tipo de cambio BCE, 07-jun-2026: 1 EUR = 1.1529 USD).
Los datos se pierden al reiniciar el servidor — suficiente para demo y evaluación.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

Phase = Literal["artwork", "package", "narrative"]

# USD por millón de tokens (input / output) — precios oficiales junio 2026
# Fuentes: docs.anthropic.com/pricing · ai.google.dev/gemini-api/docs/pricing · openai.com/api/pricing
_PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":         ( 3.00,  15.00),  # Anthropic
    "claude-haiku-4-5-20251001": ( 1.00,   5.00),  # Anthropic
    "gemini-2.5-flash":          ( 0.30,   2.50),  # Google — text/image/video (sin thinking)
    "gemini-2.5-flash-lite":     ( 0.10,   0.40),  # Google
    "gpt-4o":                    ( 2.50,  10.00),  # OpenAI
    "gpt-4o-mini":               ( 0.15,   0.60),  # OpenAI
}

# Tipo de cambio BCE 07-jun-2026: 1 EUR = 1.1529 USD
_USD_TO_EUR = 1 / 1.1529


@dataclass
class CallRecord:
    ts:        datetime
    provider:  str
    model:     str
    phase:     Phase
    tokens_in: int
    tokens_out: int
    cost_eur:  float


_log: list[CallRecord] = []


def record(provider: str, model: str, phase: Phase, tokens_in: int, tokens_out: int) -> None:
    price_in, price_out = _PRICES.get(model, (0.0, 0.0))
    cost_usd = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
    cost_eur = cost_usd * _USD_TO_EUR
    _log.append(CallRecord(
        ts=datetime.now(timezone.utc),
        provider=provider, model=model, phase=phase,
        tokens_in=tokens_in, tokens_out=tokens_out, cost_eur=cost_eur,
    ))
    logger.info(
        "usage provider=%s model=%s phase=%s in=%d out=%d cost=€%.5f",
        provider, model, phase, tokens_in, tokens_out, cost_eur,
    )


def get_summary() -> dict:
    """Agrega registros por proveedor y devuelve un resumen de uso y coste en EUR."""
    if not _log:
        return {"total_validations": 0, "by_provider": {}, "total_cost_eur": 0.0}

    by_provider: dict[str, dict] = {}
    for rec in _log:
        entry = by_provider.setdefault(rec.provider, {
            "validations": 0,
            "tokens_in":   0,
            "tokens_out":  0,
            "cost_eur":    0.0,
        })
        entry["tokens_in"]  += rec.tokens_in
        entry["tokens_out"] += rec.tokens_out
        entry["cost_eur"]   += rec.cost_eur
        if rec.phase == "artwork":
            entry["validations"] += 1

    for entry in by_provider.values():
        v = entry["validations"] or 1
        entry["avg_cost_eur"] = round(entry["cost_eur"] / v, 5)
        entry["cost_eur"]     = round(entry["cost_eur"], 5)

    return {
        "total_validations": sum(e["validations"] for e in by_provider.values()),
        "by_provider":       by_provider,
        "total_cost_eur":    round(sum(r.cost_eur for r in _log), 5),
    }
