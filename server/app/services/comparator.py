"""Comparación determinista artwork vs. embalaje — INCI y checklist regulatorio.

Algoritmos:
  - JaroWinkler + token_sort_ratio (máximo) para similitud entre nombres INCI.
  - Greedy matching para aparear ingredientes entre artwork y embalaje.
  - LIS (Longest Increasing Subsequence) para detectar cambios de orden.
"""
from __future__ import annotations

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from app.models.label import ArtworkLabel, InciLabel
from app.models.schemas import (
    ChecklistItem, Discrepancy, DifferenceType, Severity, ValidationReport, Verdict,
)

MATCH_THRESHOLD = 0.92  # Por encima → match exacto.
OCR_NOISE_LOW   = 0.86  # Entre ambos umbrales → posible error de lectura OCR.

_CHECKLIST_LABELS: dict[str, str] = {
    "ean":               "Código de barras (EAN)",
    "manufacturer":      "Fabricante / dirección",
    "pao":               "PAO — caducidad tras apertura",
    "country_of_origin": "País de fabricación",
    "warnings":          "Advertencias / precauciones",
    "net_content":       "Peso / volumen neto",
    "lot_number":        "Número de lote",
    "website":           "Sitio web",
}


# Similitud combinada: máximo entre JaroWinkler y token_sort_ratio.
def _sim(a: str, b: str) -> float:
    jw = JaroWinkler.normalized_similarity(a, b)
    tr = fuzz.token_sort_ratio(a, b) / 100.0
    return max(jw, tr)


# Devuelve los índices que forman el LIS sobre seq (para detectar reordenados).
def _lis_indices(seq: list[int]) -> set[int]:
    if not seq:
        return set()
    dp, parent = [1] * len(seq), [-1] * len(seq)
    for i in range(1, len(seq)):
        for j in range(i):
            if seq[j] < seq[i] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                parent[i] = j
    last, in_lis = dp.index(max(dp)), set()
    while last != -1:
        in_lis.add(last)
        last = parent[last]
    return in_lis


# Compara dos listas INCI con greedy matching y devuelve las discrepancias.
# check_order=False para zonas donde el orden no está regulado (may_contain).
def _compare_inci(zone: str, artwork: list[str], package: list[str], *, check_order: bool = True) -> list[Discrepancy]:
    diffs: list[Discrepancy] = []
    if not artwork and not package:
        return diffs

    candidates = sorted(
        [(i, j, _sim(artwork[i], package[j]))
         for i in range(len(artwork)) for j in range(len(package))],
        key=lambda x: -x[2],
    )
    art_matched: dict[int, tuple[int, float]] = {}
    pkg_used: set[int] = set()
    for i, j, s in candidates:
        if i in art_matched or j in pkg_used:
            continue
        if s >= OCR_NOISE_LOW:
            art_matched[i] = (j, s)
            pkg_used.add(j)

    for i, a in enumerate(artwork):
        if i in art_matched:
            j, s = art_matched[i]
            if s < MATCH_THRESHOLD:
                diffs.append(Discrepancy(
                    zone=zone, diff_type=DifferenceType.POSIBLE_ERROR_LECTURA,
                    artwork_value=a, package_value=package[j],
                    similarity_score=round(s, 3),
                    note="Similitud alta pero no exacta — revisar manualmente.",
                    severity=Severity.CRITICO,
                ))
        else:
            diffs.append(Discrepancy(
                zone=zone, diff_type=DifferenceType.FALTA_EN_FOTO,
                artwork_value=a, severity=Severity.CRITICO,
            ))

    for j, p in enumerate(package):
        if j not in pkg_used:
            diffs.append(Discrepancy(
                zone=zone, diff_type=DifferenceType.SOBRA_EN_FOTO,
                package_value=p, severity=Severity.CRITICO,
            ))

    # El orden solo es obligatorio en ingredientes (Art. 19.1.g EU 1223/2009).
    # Los colorantes opcionales (may_contain) no tienen orden regulado.
    if check_order:
        paired        = sorted(art_matched.items(), key=lambda x: x[0])
        pkg_positions = [j for _, (j, _) in paired]
        in_lis        = _lis_indices(pkg_positions)
        for idx, (i, (j, _)) in enumerate(paired):
            if idx not in in_lis:
                diffs.append(Discrepancy(
                    zone=zone, diff_type=DifferenceType.ORDEN_ALTERADO,
                    artwork_value=artwork[i], package_value=package[j],
                    note="Orden alterado respecto al artwork.",
                    severity=Severity.CRITICO,
                ))

    return diffs


# Construye el ValidationReport completo a partir de artwork y package extraídos.
def build_report(artwork: ArtworkLabel, package: InciLabel) -> ValidationReport:
    all_diffs: list[Discrepancy] = []

    all_diffs.extend(_compare_inci("ingredients", artwork.ingredients, package.ingredients, check_order=True))
    if artwork.may_contain or package.may_contain:
        all_diffs.extend(_compare_inci("may_contain", artwork.may_contain, package.may_contain, check_order=False))

    checklist = [
        ChecklistItem(
            key=key, label=label,
            in_artwork=getattr(artwork.checklist, key),
            in_package=getattr(package.checklist, key),
        )
        for key, label in _CHECKLIST_LABELS.items()
    ]

    confirmed = [d for d in all_diffs if d.diff_type != DifferenceType.POSIBLE_ERROR_LECTURA]
    verdict   = Verdict.APROBADO if not confirmed else Verdict.REVISION_REQUERIDA

    if verdict == Verdict.APROBADO:
        ocr = [d for d in all_diffs if d.diff_type == DifferenceType.POSIBLE_ERROR_LECTURA]
        summary = "Ingredientes coinciden con el artwork aprobado."
        if ocr:
            summary += f" {len(ocr)} posible(s) diferencia(s) OCR para revisar."
    else:
        summary = f"{len(confirmed)} discrepancia(s) en ingredientes. Revisión requerida."

    zone_values = {
        "ingredients": {"artwork": artwork.ingredients, "package": package.ingredients},
        "may_contain": {"artwork": artwork.may_contain, "package": package.may_contain},
    }

    return ValidationReport(
        verdict=verdict,
        summary=summary,
        discrepancies=all_diffs,
        zone_values=zone_values,
        checklist=checklist,
    )
