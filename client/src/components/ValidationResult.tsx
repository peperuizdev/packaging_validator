import { Check, X, Download, Minus } from 'lucide-react'
import type { ValidationReport, Discrepancy, DifferenceType, ChecklistItem } from '../api/types'
import { IngredientDiff } from './IngredientDiff'

interface Props {
  report:   ValidationReport
  provider: string
}

function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/_(.+?)_/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/^#+\s+/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .trim()
}

const ZONE_LABELS: Record<string, string> = {
  ingredients: 'Ingredientes INCI',
  may_contain: 'Colorantes opcionales (MAY CONTAIN)',
}

const DIFF_LABELS: Record<DifferenceType, string> = {
  falta_en_foto:         'Solo en artwork',
  sobra_en_foto:         'Solo en embalaje',
  orden_alterado:        'Orden distinto',
  posible_error_lectura: 'Revisar OCR',
}

const PROVIDER_LABELS: Record<string, string> = {
  claude: 'Claude Sonnet · Anthropic',
  gemini: 'Gemini 2.5 Flash · Google',
  openai: 'GPT-4o · OpenAI',
}

// ── Cabecera de veredicto ─────────────────────────────────────────────────────

function VerdictHeader({ report, provider }: { report: ValidationReport; provider: string }) {
  const ok       = report.verdict === 'APROBADO'
  const critical = report.discrepancies.filter(d => d.diff_type !== 'posible_error_lectura').length
  const ocr      = report.discrepancies.filter(d => d.diff_type === 'posible_error_lectura').length

  return (
    <div className="bg-white border border-stone-200 shadow-sm rounded-xl px-6 py-5">
      <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${ok ? 'bg-emerald-500' : 'bg-rose-500'}`}>
              {ok
                ? <Check className="w-3 h-3 text-white" strokeWidth={3} />
                : <X     className="w-3 h-3 text-white" strokeWidth={3} />
              }
            </div>
            <p className="text-base font-semibold text-stone-900 leading-tight">
              {ok ? 'Validación superada' : 'Revisión requerida'}
            </p>
          </div>
          <span className="text-xs text-stone-400 shrink-0 hidden sm:block pt-0.5">
            {PROVIDER_LABELS[provider] ?? provider}
          </span>
        </div>

        {/* Valoración narrativa del LLM */}
        {(report.narrative || report.summary) && (
          <p className="mt-3 text-sm text-stone-600 leading-relaxed pl-8">
            {stripMarkdown(report.narrative || report.summary)}
          </p>
        )}

        {/* Estadísticas */}
        {(critical > 0 || ocr > 0) && (
          <div className="mt-4 pt-4 border-t border-stone-100 flex flex-wrap gap-6 text-xs text-stone-500 pl-8">
            {critical > 0 && (
              <span>
                <span className="font-semibold text-stone-800">{critical}</span>
                {' '}discrepancia{critical > 1 ? 's' : ''} detectada{critical > 1 ? 's' : ''}
              </span>
            )}
            {ocr > 0 && (
              <span>
                <span className="font-semibold text-stone-700">{ocr}</span>
                {' '}coincidencia{ocr > 1 ? 's' : ''} aproximada{ocr > 1 ? 's' : ''} — revisar manualmente
              </span>
            )}
          </div>
        )}
    </div>
  )
}

// ── Sección de zona ───────────────────────────────────────────────────────────

function ZoneSection({
  zone,
  artworkValues,
  packageValues,
  discrepancies,
}: {
  zone:          string
  artworkValues: string[]
  packageValues: string[]
  discrepancies: Discrepancy[]
}) {
  const confirmed = discrepancies.filter(d => d.diff_type !== 'posible_error_lectura')
  const ocrCount  = discrepancies.length - confirmed.length

  return (
    <div className="bg-white border border-stone-200 shadow-sm rounded-xl px-6 py-5">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-sm font-semibold text-stone-900">{ZONE_LABELS[zone] ?? zone}</h2>
        <span className={`text-xs font-medium ${
          confirmed.length > 0 ? 'text-rose-600' :
          ocrCount > 0        ? 'text-amber-600' :
                                'text-emerald-600'
        }`}>
          {confirmed.length > 0
            ? `${confirmed.length} diferencia${confirmed.length > 1 ? 's' : ''}${ocrCount > 0 ? ` · ${ocrCount} OCR` : ''}`
            : ocrCount > 0
              ? `${ocrCount} revisar OCR`
              : 'Sin diferencias'
          }
        </span>
      </div>

      <IngredientDiff
        artworkItems={artworkValues}
        packageItems={packageValues}
        discrepancies={discrepancies}
        zone={zone}
      />
    </div>
  )
}

// ── Checklist regulatorio ─────────────────────────────────────────────────────

function StatusIcon({ present }: { present: boolean }) {
  return present
    ? <Check className="w-3.5 h-3.5 text-emerald-600" strokeWidth={2.5} />
    : <Minus className="w-3.5 h-3.5 text-stone-300" strokeWidth={2} />
}

function ChecklistSection({ items }: { items: ChecklistItem[] }) {
  if (items.length === 0) return null

  // Campos que aparecen en artwork pero no en embalaje (discrepancias reales)
  const mismatches = items.filter(i => i.in_artwork && !i.in_package)

  return (
    <div className="bg-white border border-stone-200 shadow-sm rounded-xl px-6 py-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-stone-900">
          Checklist obligatorio — EU 1223/2009 Art. 19
        </h2>
        <span className={`text-xs font-medium ${mismatches.length === 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
          {mismatches.length === 0
            ? 'Sin discrepancias'
            : `${mismatches.length} campo${mismatches.length > 1 ? 's' : ''} no detectado${mismatches.length > 1 ? 's' : ''} en embalaje`
          }
        </span>
      </div>

      {/* Tabla de campos — label + indicadores Artwork/Embalaje */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left font-semibold text-stone-400 uppercase tracking-wide pb-2 pr-4">Campo</th>
              <th className="text-center font-semibold text-stone-400 uppercase tracking-wide pb-2 px-3 whitespace-nowrap">Artwork</th>
              <th className="text-center font-semibold text-stone-400 uppercase tracking-wide pb-2 pl-3 whitespace-nowrap">Embalaje</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-50">
            {items.map(item => {
              const mismatch = item.in_artwork && !item.in_package
              return (
                <tr key={item.key} className={mismatch ? 'bg-stone-50' : ''}>
                  <td className={`py-2 pr-4 ${mismatch ? 'text-stone-700 font-medium' : 'text-stone-500'}`}>
                    {item.label}
                  </td>
                  <td className="py-2 px-3">
                    <span className="flex justify-center"><StatusIcon present={item.in_artwork} /></span>
                  </td>
                  <td className="py-2 pl-3">
                    <span className="flex justify-center"><StatusIcon present={item.in_package} /></span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] text-stone-400 mt-3 border-t border-stone-100 pt-3">
        Presencia detectada automáticamente. La validez del valor de cada campo requiere revisión manual.
      </p>
    </div>
  )
}

// ── Generación y descarga del informe ────────────────────────────────────────

function buildTextReport(report: ValidationReport, provider: string): string {
  const lines = [
    'Packaging Validator — INFORME DE VALIDACIÓN',
    '========================================',
    '',
    `Veredicto: ${report.verdict === 'APROBADO' ? 'Validación superada' : 'Revisión requerida'}`,
    `Resumen:   ${report.summary}`,
    `Proveedor: ${PROVIDER_LABELS[provider] ?? provider}`,
    '',
  ]

  for (const zone of ['ingredients', 'may_contain']) {
    const sides = report.zone_values?.[zone]
    if (!sides || (sides.artwork.length === 0 && sides.package.length === 0)) continue
    const diffs = report.discrepancies.filter(d => d.zone === zone)

    lines.push(`\n[${(ZONE_LABELS[zone] ?? zone).toUpperCase()}]`)
    lines.push(`  Artwork  (${sides.artwork.length}): ${sides.artwork.join(', ') || '(sin datos)'}`)
    lines.push(`  Embalaje (${sides.package.length}): ${sides.package.join(', ') || '(sin datos)'}`)

    if (diffs.length > 0) {
      lines.push('  Diferencias:')
      for (const d of diffs) {
        const a = d.artwork_value  ? `Artwork: "${d.artwork_value}"` : ''
        const p = d.package_value  ? `Embalaje: "${d.package_value}"` : ''
        lines.push(`    • ${DIFF_LABELS[d.diff_type]}: ${[a, p].filter(Boolean).join(' | ')}`)
      }
    }
  }

  if (report.checklist.length > 0) {
    lines.push('\n[CHECKLIST EU 1223/2009 Art. 19]')
    for (const item of report.checklist) {
      lines.push(`  ${item.in_artwork ? '✓' : '–'} Artwork  ${item.in_package ? '✓' : '–'} Embalaje  ${item.label}`)
    }
  }

  lines.push('')
  lines.push('---')
  lines.push('Nota: se verifica únicamente el contenido textual de la lista de ingredientes.')
  lines.push('El checklist regulatorio y los valores de cada campo requieren revisión manual.')
  return lines.join('\n')
}

function downloadReport(report: ValidationReport, provider: string) {
  const blob = new Blob([buildTextReport(report, provider)], { type: 'text/plain;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `validacion-${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Componente principal ──────────────────────────────────────────────────────

export function ValidationResult({ report, provider }: Props) {
  const byZone = report.discrepancies.reduce<Record<string, Discrepancy[]>>((acc, d) => {
    ;(acc[d.zone] ??= []).push(d)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <VerdictHeader report={report} provider={provider} />

      {['ingredients', 'may_contain'].map(zone => {
        const sides = report.zone_values?.[zone] ?? { artwork: [], package: [] }
        if (sides.artwork.length === 0 && sides.package.length === 0) return null
        return (
          <ZoneSection
            key={zone}
            zone={zone}
            artworkValues={sides.artwork}
            packageValues={sides.package}
            discrepancies={byZone[zone] ?? []}
          />
        )
      })}

      <ChecklistSection items={report.checklist} />

      <div className="flex items-center justify-between pt-1 pb-6">
        <p className="text-xs text-stone-400 max-w-sm">
          Solo se verifica el contenido textual de los ingredientes.
          El resto de campos requieren validación humana.
        </p>
        <button
          type="button"
          onClick={() => downloadReport(report, provider)}
          className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 hover:bg-stone-50 transition-colors shrink-0"
        >
          <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
          Exportar informe
        </button>
      </div>
    </div>
  )
}
