"""Modelos internos de etiqueta y utilidades de parseo/limpieza de INCI."""
from __future__ import annotations

import json
import re

from pydantic import BaseModel

# Caracteres válidos en nombres INCI y colorantes CI.
_INCI_RE = re.compile(r"^[A-Z0-9\s\-\(\)/,\.\'\*\+&]+$")


class RegulatoryChecklist(BaseModel):
    ean:               bool = False
    manufacturer:      bool = False
    pao:               bool = False
    country_of_origin: bool = False
    warnings:          bool = False
    net_content:       bool = False
    lot_number:        bool = False
    website:           bool = False


class InciLabel(BaseModel):
    ingredients: list[str] = []
    may_contain: list[str] = []
    checklist:   RegulatoryChecklist = RegulatoryChecklist()


class ArtworkLabel(BaseModel):
    ingredients: list[str] = []
    may_contain: list[str] = []
    checklist:   RegulatoryChecklist = RegulatoryChecklist()


# ── Parseo JSON ───────────────────────────────────────────────────────────────

# Parsea la respuesta del LLM tolerando fences de markdown (```json ... ```).
def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise RuntimeError("El modelo no devolvió un JSON válido.")
        return json.loads(m.group())


# ── Limpieza de listas INCI ───────────────────────────────────────────────────

# Acepta solo nombres INCI: letras, dígitos y caracteres de nomenclatura química.
def _is_valid_inci(name: str) -> bool:
    if len(name) < 2 or len(name) > 120:
        return False
    if not _INCI_RE.match(name.upper()):
        return False
    if re.fullmatch(r"[\d\s\-\.]+", name):
        return False
    return True


# Elimina duplicados preservando el orden de aparición.
def _dedupe_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# Normaliza a mayúsculas, filtra entradas inválidas y deduplica.
def _clean_inci_list(raw: list[str]) -> list[str]:
    return _dedupe_ordered([
        i.strip().upper() for i in raw
        if i.strip() and _is_valid_inci(i.strip())
    ])


# Convierte a lista un campo que el LLM devolvió como string en lugar de array.
def _coerce_lists(data: dict, fields: list[str]) -> None:
    for f in fields:
        if f in data and isinstance(data[f], str):
            data[f] = [data[f]] if data[f].strip() else []


# ── Constructores de modelos limpios ─────────────────────────────────────────

# Extrae el checklist del dict del LLM; acepta anidado o plano (fallback).
def _extract_checklist(data: dict) -> RegulatoryChecklist:
    checklist_raw = data.get("checklist")
    if not isinstance(checklist_raw, dict):
        checklist_raw = {f: data.get(f, False) for f in RegulatoryChecklist.model_fields}
    return RegulatoryChecklist.model_validate(checklist_raw)


# Construye un InciLabel normalizado a partir del dict devuelto por el LLM.
def clean_inci(data: dict) -> InciLabel:
    _coerce_lists(data, ["ingredients", "may_contain"])
    return InciLabel(
        ingredients=_clean_inci_list(data.get("ingredients", [])),
        may_contain=_clean_inci_list(data.get("may_contain", [])),
        checklist=_extract_checklist(data),
    )


# Construye un ArtworkLabel normalizado; soporta checklist anidado o plano.
def clean_artwork(data: dict) -> ArtworkLabel:
    _coerce_lists(data, ["ingredients", "may_contain"])
    return ArtworkLabel(
        ingredients=_clean_inci_list(data.get("ingredients", [])),
        may_contain=_clean_inci_list(data.get("may_contain", [])),
        checklist=_extract_checklist(data),
    )
