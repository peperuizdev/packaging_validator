"""Tests de las capas core: parseo INCI y comparación de etiquetas."""
from __future__ import annotations

import json

import pytest

from app.models.label import (
    ArtworkLabel,
    InciLabel,
    RegulatoryChecklist,
    clean_artwork,
    clean_inci,
    parse_json,
)
from app.models.schemas import DifferenceType, Severity, Verdict
from app.services.comparator import _compare_inci, build_report

RICINUS     = "RICINUS COMMUNIS (CASTOR) SEED OIL"
TOCOPHEROL  = "TOCOPHEROL"
BEESWAX     = "BEESWAX"
CARNAUBA    = "COPERNICIA CERIFERA (CARNAUBA) WAX"
DIMETHICONE = "DIMETHICONE"


# ── parse_json ────────────────────────────────────────────────────────────────

class TestParseJson:
    def test_clean_json(self):
        raw = json.dumps({"ingredients": [], "may_contain": []})
        assert parse_json(raw) == {"ingredients": [], "may_contain": []}

    def test_markdown_fence_stripped(self):
        raw = "```json\n" + json.dumps({"ingredients": []}) + "\n```"
        assert "ingredients" in parse_json(raw)

    def test_invalid_raises(self):
        with pytest.raises(RuntimeError):
            parse_json("esto no es JSON")


# ── clean_inci ────────────────────────────────────────────────────────────────

class TestCleanInci:
    def test_upcases_and_strips(self):
        result = clean_inci({"ingredients": [" tocopherol "], "may_contain": []})
        assert result.ingredients == ["TOCOPHEROL"]

    def test_deduplicates(self):
        result = clean_inci({"ingredients": [TOCOPHEROL, TOCOPHEROL], "may_contain": []})
        assert result.ingredients == [TOCOPHEROL]

    def test_coerces_string_to_list(self):
        result = clean_inci({"ingredients": TOCOPHEROL, "may_contain": []})
        assert result.ingredients == [TOCOPHEROL]

    def test_filters_invalid_entries(self):
        result = clean_inci({"ingredients": [TOCOPHEROL, "123", ""], "may_contain": []})
        assert result.ingredients == [TOCOPHEROL]

    def test_colorants_with_same_ci_kept_separate(self):
        colorants = ["CI 15850 (RED 6)", "CI 15850 (RED 7 LAKE)"]
        result = clean_inci({"ingredients": [], "may_contain": colorants})
        assert len(result.may_contain) == 2


# ── clean_artwork ─────────────────────────────────────────────────────────────

class TestCleanArtwork:
    def test_nested_checklist(self):
        data = {
            "ingredients": [TOCOPHEROL],
            "may_contain": [],
            "checklist": {"ean": True, "manufacturer": False, "pao": False,
                          "country_of_origin": False, "warnings": False,
                          "net_content": False, "lot_number": False, "website": False},
        }
        result = clean_artwork(data)
        assert result.checklist.ean is True

    def test_flat_checklist_fallback(self):
        # Si el modelo devuelve los booleanos al nivel raíz en lugar de anidados.
        data = {
            "ingredients": [TOCOPHEROL],
            "may_contain": [],
            "ean": True, "manufacturer": False, "pao": False,
            "country_of_origin": False, "warnings": False,
            "net_content": False, "lot_number": False, "website": False,
        }
        result = clean_artwork(data)
        assert result.checklist.ean is True


# ── _compare_inci ─────────────────────────────────────────────────────────────

class TestCompareInci:
    def test_identical_no_diffs(self):
        items = [RICINUS, TOCOPHEROL, BEESWAX]
        assert _compare_inci("ingredients", items, items) == []

    def test_empty_no_diffs(self):
        assert _compare_inci("ingredients", [], []) == []

    def test_missing_in_package(self):
        diffs = _compare_inci("ingredients", [RICINUS, TOCOPHEROL, BEESWAX], [RICINUS, BEESWAX])
        missing = [d for d in diffs if d.diff_type == DifferenceType.FALTA_EN_FOTO]
        assert len(missing) == 1
        assert missing[0].artwork_value == TOCOPHEROL

    def test_extra_in_package(self):
        diffs = _compare_inci("ingredients", [RICINUS, BEESWAX], [RICINUS, DIMETHICONE, BEESWAX])
        extra = [d for d in diffs if d.diff_type == DifferenceType.SOBRA_EN_FOTO]
        assert len(extra) == 1
        assert extra[0].package_value == DIMETHICONE

    def test_order_change_detected(self):
        artwork = [RICINUS, TOCOPHEROL, BEESWAX, CARNAUBA]
        package = [RICINUS, BEESWAX, TOCOPHEROL, CARNAUBA]
        diffs = _compare_inci("ingredients", artwork, package)
        assert any(d.diff_type == DifferenceType.ORDEN_ALTERADO for d in diffs)

    def test_ocr_typo_does_not_generate_missing_or_extra(self):
        # Transposición de un carácter: similitud > MATCH_THRESHOLD → match exacto, sin diff.
        diffs = _compare_inci("ingredients", ["TITANIUM DIOXIDE", BEESWAX], ["TITAINUM DIOXIDE", BEESWAX])
        assert not any(d.diff_type in (DifferenceType.FALTA_EN_FOTO, DifferenceType.SOBRA_EN_FOTO) for d in diffs)

    def test_severity_always_critico(self):
        diffs = _compare_inci("ingredients", [RICINUS], [DIMETHICONE])
        assert all(d.severity == Severity.CRITICO for d in diffs)


# ── build_report ──────────────────────────────────────────────────────────────

def _make_artwork(ingredients, may_contain=None, **checklist_kwargs) -> ArtworkLabel:
    checklist = RegulatoryChecklist(**checklist_kwargs)
    return ArtworkLabel(
        ingredients=ingredients,
        may_contain=may_contain or [],
        checklist=checklist,
    )

def _make_package(ingredients, may_contain=None) -> InciLabel:
    return InciLabel(ingredients=ingredients, may_contain=may_contain or [])


class TestBuildReport:
    def test_identical_labels_aprobado(self):
        artwork = _make_artwork([RICINUS, TOCOPHEROL])
        package = _make_package([RICINUS, TOCOPHEROL])
        report = build_report(artwork, package)
        assert report.verdict == Verdict.APROBADO
        assert report.discrepancies == []

    def test_missing_ingredient_revision_requerida(self):
        artwork = _make_artwork([RICINUS, TOCOPHEROL, BEESWAX])
        package = _make_package([RICINUS, BEESWAX])
        report = build_report(artwork, package)
        assert report.verdict == Verdict.REVISION_REQUERIDA
        missing = [d for d in report.discrepancies if d.diff_type == DifferenceType.FALTA_EN_FOTO]
        assert len(missing) == 1

    def test_ocr_noise_only_is_aprobado(self):
        artwork = _make_artwork(["TITANIUM DIOXIDE"])
        package = _make_package(["TITAINUM DIOXIDE"])
        assert build_report(artwork, package).verdict == Verdict.APROBADO

    def test_checklist_in_report(self):
        artwork = _make_artwork([RICINUS], ean=True, manufacturer=True)
        package = _make_package([RICINUS])
        report = build_report(artwork, package)
        ean_item = next(i for i in report.checklist if i.key == "ean")
        assert ean_item.in_artwork is True
        assert ean_item.in_package is False

    def test_zone_values_populated(self):
        artwork = _make_artwork([RICINUS], may_contain=["CI 77891"])
        package = _make_package([RICINUS], may_contain=["CI 77891"])
        report = build_report(artwork, package)
        assert report.zone_values["ingredients"]["artwork"] == [RICINUS]
        assert report.zone_values["may_contain"]["artwork"] == ["CI 77891"]
