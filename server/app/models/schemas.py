from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class DifferenceType(str, Enum):
    FALTA_EN_FOTO         = "falta_en_foto"
    SOBRA_EN_FOTO         = "sobra_en_foto"
    ORDEN_ALTERADO        = "orden_alterado"
    POSIBLE_ERROR_LECTURA = "posible_error_lectura"


class Severity(str, Enum):
    CRITICO = "critico"
    MEDIO   = "medio"


class Verdict(str, Enum):
    APROBADO           = "APROBADO"
    REVISION_REQUERIDA = "REVISION_REQUERIDA"


class Discrepancy(BaseModel):
    zone:             str
    diff_type:        DifferenceType
    artwork_value:    Optional[str]   = None
    package_value:    Optional[str]   = None
    note:             Optional[str]   = None
    severity:         Severity
    similarity_score: Optional[float] = None


class ChecklistItem(BaseModel):
    key:        str
    label:      str
    in_artwork: bool
    in_package: bool


class ValidationReport(BaseModel):
    verdict:       Verdict
    summary:       str
    narrative:     str = ""  # valoración global generada por LLM pequeño
    discrepancies: list[Discrepancy]
    zone_values:   dict[str, dict[str, list[str]]]
    checklist:     list[ChecklistItem] = []
