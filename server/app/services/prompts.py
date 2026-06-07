"""Prompts de extracción y valoración — EU Regulation 1223/2009 Art. 19."""
from __future__ import annotations

from app.models.schemas import DifferenceType, ValidationReport

PROMPT_ARTWORK = """\
You are performing verbatim text extraction from a cosmetics packaging artwork (EU Regulation 1223/2009).
Your task is transcription — do not apply chemistry knowledge, do not merge or group names.

Extract ONLY from the consumer label panel (the colored rectangle labeled EXTÉRIEUR or equivalent).
Ignore: DATA_SAP tables, filenames, print specifications, colour swatches.

Output this JSON only — no prose, no markdown:
{
  "ingredients": [],
  "may_contain": [],
  "checklist": {
    "ean": false,
    "manufacturer": false,
    "pao": false,
    "country_of_origin": false,
    "warnings": false,
    "net_content": false,
    "lot_number": false,
    "website": false
  }
}

Rules:
- ingredients: split the INCI section at every comma — one array element per token.
  Each comma in the source creates exactly one new element, even if adjacent names could be read as a single compound.
  Parentheses are part of the token — never split on them.
  A line break in the middle of a name is a continuation — do NOT start a new element.
  Only a comma starts a new element.
  Stop at the first (+/-) or [(+/-)] token.

- may_contain: split the text after (+/-) at every comma — one array element per token.
  Each comma in the source creates exactly one new element.
  A line break mid-name is a continuation — only commas separate elements.
  Tokens that share a CI number but differ in any other character are separate elements — include every one.
  [] if absent.

- checklist: true if detectable anywhere in the consumer label, false if absent.
  Detect presence only — do not extract values.
  • ean: barcode (8 or 13 digits)
  • manufacturer: brand or company name and address
  • pao: open-jar symbol with a number and M
  • country_of_origin: country of manufacture
  • warnings: precautionary phrases or usage restrictions
  • net_content: weight or volume
  • lot_number: batch or lot reference
  • website: web URL
"""

PROMPT_PACKAGE = """\
You are performing verbatim text extraction from photos of a physical cosmetics package (EU Regulation 1223/2009).
Your task is transcription — do not apply chemistry knowledge, do not merge or group names.
Read every photo to build the complete ingredient list and detect regulatory fields.

Output this JSON only — no prose, no markdown:
{
  "ingredients": [],
  "may_contain": [],
  "checklist": {
    "ean": false,
    "manufacturer": false,
    "pao": false,
    "country_of_origin": false,
    "warnings": false,
    "net_content": false,
    "lot_number": false,
    "website": false
  }
}

Rules:
- ingredients: split the INCI section at every comma — one array element per token.
  Each comma in the source creates exactly one new element, even if adjacent names could be read as a single compound.
  Parentheses are part of the token — never split on them.
  A line break in the middle of a name is a continuation — do NOT start a new element.
  Only a comma starts a new element.
  Stop at the first (+/-) or [(+/-)] token.

- may_contain: split the text after (+/-) at every comma — one array element per token.
  Each comma in the source creates exactly one new element.
  A line break mid-name is a continuation — only commas separate elements.
  Tokens that share a CI number but differ in any other character are separate elements — include every one.
  Check every photo — this section may appear on a different face. [] if absent.

- checklist: true if detectable in any of the photos, false if absent or not visible.
  Detect presence only — do not extract values.
  • ean: barcode (8 or 13 digits)
  • manufacturer: brand or company name and address
  • pao: open-jar symbol with a number and M
  • country_of_origin: country of manufacture
  • warnings: precautionary phrases or usage restrictions
  • net_content: weight or volume
  • lot_number: batch or lot reference
  • website: web URL
"""


def build_narrative_prompt(report: ValidationReport) -> str:
    """Construye el prompt para que un LLM pequeño genere una valoración global en español."""
    n_crit = sum(1 for d in report.discrepancies
                 if d.diff_type != DifferenceType.POSIBLE_ERROR_LECTURA)
    n_ocr  = sum(1 for d in report.discrepancies
                 if d.diff_type == DifferenceType.POSIBLE_ERROR_LECTURA)
    missing = [i.label for i in report.checklist if i.in_artwork and not i.in_package]

    facts = [f"Veredicto: {report.verdict.value}"]
    if n_crit:
        facts.append(f"Discrepancias confirmadas en ingredientes INCI: {n_crit}")
    if n_ocr:
        facts.append(f"Posibles errores de lectura OCR que requieren revisión manual: {n_ocr}")
    if missing:
        facts.append(f"Campos del Art. 19 no detectados en embalaje: {', '.join(missing)}")
    if not n_crit and not n_ocr and not missing:
        facts.append("Sin discrepancias en ingredientes ni en checklist regulatorio")

    data = "\n".join(f"- {f}" for f in facts)
    return (
        "You are a regulatory compliance specialist for EU cosmetics packaging (Regulation 1223/2009).\n"
        "Write a concise professional assessment in Spanish (2–3 sentences) for the R&D/QC team.\n"
        "Be direct and actionable. Synthesize — do not repeat numbers literally.\n"
        "Plain text only — no markdown, no asterisks, no bullet points.\n\n"
        f"Validation data:\n{data}\n\nAssessment:"
    )
