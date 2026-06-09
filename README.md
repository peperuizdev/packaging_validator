# Packaging Validator — Validación de Packaging Cosmético EU 1223/2009

Herramienta de QC que compara el artwork aprobado de un cosmético (PDF de imprenta) contra fotos del embalaje físico y detecta discrepancias antes de que el producto llegue a mercado.

---

## Historias de usuario

**H1 — Técnico de control de calidad**
> Como técnico de QC, quiero subir el PDF del artwork aprobado junto con fotos del embalaje físico fabricado y obtener automáticamente una lista de discrepancias en los ingredientes INCI, para poder decidir si el lote es apto para distribución sin tener que comparar manualmente campo a campo.

**H2 — Especialista en asuntos regulatorios**
> Como especialista regulatorio, quiero verificar que todos los campos obligatorios del Art. 19 del Reglamento (CE) 1223/2009 están presentes en el embalaje físico (EAN, fabricante, PAO, advertencias, contenido neto, número de lote, web), para asegurar la conformidad antes de la puesta en mercado y evitar sanciones o retiradas.

---

## Arquitectura

```
Frontend (React + Vite + TypeScript)
        │
        │  POST /api/validate  (multipart: PDF + 1-2 fotos + provider)
        ▼
Backend (FastAPI + asyncio.to_thread)
        │
        ├── _extract_artwork(pdf_bytes)
        │       Claude  → PDF nativo base64 (lectura vectorial)
        │       Gemini  → PDF rasterizado a PNG 200dpi (OCR visual — ver decisión 3)
        │       OpenAI  → PDF como data URL (Responses API)
        │
        ├── _extract_package(photo_bytes_list)
        │       Los tres proveedores reciben las fotos como imágenes JPEG
        │
        │   Salida de ambas extracciones: JSON estructurado
        │   { ingredients[], may_contain[], checklist{} }
        │
        ├── build_report(artwork, package)          ← capa determinista, sin LLM
        │       Greedy matching con JaroWinkler + token_sort_ratio
        │       LIS (Longest Increasing Subsequence) para detectar orden alterado
        │       Comparación de checklist campo a campo
        │
        └── _generate_narrative(report)             ← modelo pequeño (Haiku / Flash / gpt-4o-mini)
                Genera valoración global en español para el equipo R&D/QC
```

---

## Decisiones de diseño

### 1 · Arquitectura multi-proveedor

El sistema soporta Claude (Anthropic), Gemini (Google) y GPT-4o (OpenAI) de forma intercambiable. Cada proveedor implementa la misma interfaz `compare(pdf_bytes, photo_bytes_list) → ValidationReport`.

**Por qué**: evita dependencia de un único vendor. Ante un cambio de precios, una degradación de servicio o un bloqueo regulatorio, el equipo puede cambiar de proveedor sin tocar la lógica de comparación ni el frontend. También permite comparar calidad y coste real entre modelos en producción.

### 2 · Comparación determinista, no LLM-to-LLM

El LLM solo transcribe. Toda la lógica de comparación y veredicto es código Python determinista: greedy matching con similitud combinada (JaroWinkler + token_sort_ratio), detección de orden por LIS y comparación exacta del checklist.

**Por qué**: un LLM comparando dos listas puede alucinar coincidencias, ignorar diferencias sutiles o variar entre ejecuciones. El código determinista es reproducible, auditable y testeable con pytest. El veredicto para el mismo par (artwork, embalaje) es siempre el mismo.

### 3 · Gemini recibe el PDF rasterizado, no nativo

Para Gemini, el PDF se convierte a imágenes PNG (200dpi con PyMuPDF) antes de enviarlo. Claude y OpenAI reciben el PDF directamente.

**Por qué**: cuando Gemini lee un PDF nativo aplica conocimiento semántico y fusiona entradas INCI que reconoce como variantes del mismo compuesto. Esto rompe la comparación verbatim. El OCR visual sobre imágenes es literal y produce resultados equivalentes a los otros modelos.

### 4 · Umbrales de similitud para ruido OCR

| Similitud | Clasificación |
|-----------|--------------|
| ≥ 0.92 | Match exacto — mismo ingrediente |
| 0.86 – 0.91 | `posible_error_lectura` — match probable, revisar manualmente |
| < 0.86 | Sin match — discrepancia confirmada |

El umbral 0.92 tolera transposiciones de un carácter típicas de OCR (TITANIUM / TITAINUM) sin generar falsos positivos.

### 5 · El orden solo se valida en ingredientes, no en colorantes

`_compare_inci` aplica la detección de orden (LIS) únicamente a `ingredients`. Para `may_contain` solo verifica presencia.

**Por qué**: el Art. 19.1.g del Reglamento 1223/2009 exige orden decreciente por concentración en la lista INCI principal. Los colorantes opcionales bajo el marcador `(+/-)` están exentos de ese requisito.

### 6 · Narrativa con modelo pequeño

La valoración global en español se genera con Claude Haiku, Gemini Flash Lite o gpt-4o-mini (según el proveedor activo), no con el modelo principal.

**Por qué**: la narrativa es texto libre de 2-3 frases sobre datos ya calculados. No necesita capacidad de visión ni razonamiento complejo. Usar el modelo pequeño reduce el coste de esa llamada entre 10× y 20×.

---

## Alternativa descartada: prompting por pasos con Claude

Durante el desarrollo se probó una estrategia de extracción encadenada exclusivamente con Claude, con un prompt que extraía cada campo como valor textual real (no presencia booleana):

```
PROMPT_ARTWORK (versión Claude):

You are a cosmetics label auditor. This PDF is a packaging dieline.

CRITICAL — DO NOT READ these areas, they are printer specifications, not label content:
- Any table labeled DATA_SAP (contains production metadata — ignore every cell in it)
- Any line that looks like a filename: long strings with underscores, codes like "ART_", "BKL_"
- OUTSIDE FINISHING / INSIDE FINISHING tables, colour swatches, varnish notes

Extract ONLY from the coloured panel outlines (the rectangles labeled EXTÉRIEUR or equivalent).

Output this JSON only — no prose, no markdown:
{"ingredients":[],"may_contain":[],"ean":[],"ref_code":[],"manufacturer":[],
 "pao":[],"country_of_origin":[],"warnings":[],"claims":[],"website":[]}

Rules:
- ingredients: full INCI list in EXACT printed order (EU law: descending concentration).
  One name per element. Split at commas between names; parentheses are part of a name.
  Stop at the first (+/-) or [(+/-)] token.
- may_contain: every colorant after the (+/-) MAY CONTAIN / [(+/-) MAY CONTAIN: marker.
  Separate list. [] if absent.
- manufacturer: one element per printed line or logical block (brand / company / address line).
  Copy exactly as printed.
- claims: consumer-facing marketing phrases printed in the label panel, in ALL languages.
  One element per sentence (split at each period — do not merge two sentences into one element).
  Precaution phrases go in warnings, not here.
  Internal product codes and production references are not claims.
- warnings: precaution phrases and distribution restrictions.
- ean: 8 or 13 consecutive digits, no spaces.
- ref_code: the product SKU near the barcode, distinct from EAN. [] if absent.
- pao: digits + M from the open-jar symbol, e.g. 12M. [] if absent.
```

La estrategia encadenada usaba tres llamadas consecutivas: extraer INCI, extraer checklist campo a campo y verificar ambigüedades.

**Resultado**: tasa de detección notablemente superior con el ejemplo de referencia.

**Por qué se descartó**: dependía de características específicas de Claude (reutilización del documento entre turnos, caché de prompts). Replicarla con Gemini u OpenAI hubiera requerido arquitecturas distintas por proveedor, rompiendo la intercambiabilidad. Se priorizó un diseño agnóstico al proveedor con un único prompt por extracción.

---

## El prompt final

Un único prompt por extracción, agnóstico al proveedor. El checklist se detecta como presencia booleana para centrarse en la validación del INCI, que es el riesgo regulatorio principal.

```
PROMPT_ARTWORK:

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
```

```
PROMPT_PACKAGE:

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
```

---

## Coste y métricas

Medición real sobre una validación con 1 artwork PDF + 2 fotos de embalaje físico (junio 2026):

| Modelo | Tokens entrada | Tokens salida | Coste por validación |
|--------|---------------|--------------|----------------------|
| Claude Sonnet 4.6 | 6.746 | 1.476 | **€0,0352** |
| GPT-4o | 4.833 | 1.221 | **€0,0202** |
| Gemini 2.5 Flash | 1.661 | 1.223 | **€0,0031** |

*Tipo de cambio BCE 07-jun-2026: 1 EUR = 1,1529 USD. Precios sin thinking mode. La narrativa usa Haiku 4.5, Gemini Flash Lite o gpt-4o-mini según el proveedor activo, incluidos en los totales anteriores. El endpoint `/api/metrics` calcula y devuelve los costes en EUR en tiempo real.*

El valor económico de la automatización se calibra contra el coste de un error no detectado: una retirada de producto por etiquetado incorrecto puede superar los 100.000 € entre logística, comunicación regulatoria y daño de marca. A esa escala, miles de validaciones automáticas se amortizan con un solo incidente evitado.

---

## Puesta en marcha

### Requisitos

- Python 3.11
- Node.js ≥ 18
- Al menos una API key: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` o `OPENAI_API_KEY`

### Backend

```bash
cd server
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Crear .env con las API keys que vayas a usar
cp .env.example .env   # editar con tus claves

uvicorn app.main:app --reload --reload-dir app
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)

# Para ver las respuestas raw de los LLM en terminal:
uvicorn app.main:app --reload --reload-dir app --log-level debug
```

### Frontend

```bash
cd client
npm install
npm run dev
# → http://localhost:5173
```

### Tests

```bash
cd server
pytest tests/ -v
```

Los tests de la capa core (parseo INCI, comparador, checklist) no requieren API key ni conexión de red.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| PDF → imagen | PyMuPDF (fitz) — solo para Gemini |
| Similitud INCI | RapidFuzz: JaroWinkler + token_sort_ratio |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS |
| Modelos principales | Claude Sonnet, Gemini 2.5 Flash, GPT-4o |
| Narrativa | Claude Haiku, Gemini Flash Lite, gpt-4o-mini |
