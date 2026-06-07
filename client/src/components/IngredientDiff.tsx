import type { Discrepancy } from '../api/types'

interface Props {
  artworkItems:  string[]
  packageItems:  string[]
  discrepancies: Discrepancy[]
  zone:          string
}

type RowStatus = 'ok' | 'missing' | 'extra' | 'order' | 'ocr'

function getStatus(item: string, side: 'artwork' | 'package', discrepancies: Discrepancy[]): RowStatus {
  const u = item.toUpperCase()
  for (const d of discrepancies) {
    if (side === 'artwork') {
      if (d.diff_type === 'falta_en_foto'        && d.artwork_value?.toUpperCase() === u) return 'missing'
      if (d.diff_type === 'orden_alterado'        && d.artwork_value?.toUpperCase() === u) return 'order'
      if (d.diff_type === 'posible_error_lectura' && d.artwork_value?.toUpperCase() === u) return 'ocr'
    } else {
      if (d.diff_type === 'sobra_en_foto'         && d.package_value?.toUpperCase() === u) return 'extra'
      if (d.diff_type === 'orden_alterado'        && d.package_value?.toUpperCase() === u) return 'order'
      if (d.diff_type === 'posible_error_lectura' && d.package_value?.toUpperCase() === u) return 'ocr'
    }
  }
  return 'ok'
}

function getOrderPosition(
  item: string,
  side: 'artwork' | 'package',
  artworkItems: string[],
  packageItems: string[],
  discrepancies: Discrepancy[],
): number {
  const u = item.toUpperCase()
  for (const d of discrepancies) {
    if (d.diff_type !== 'orden_alterado') continue
    if (side === 'artwork' && d.artwork_value?.toUpperCase() === u && d.package_value)
      return packageItems.findIndex(x => x.toUpperCase() === d.package_value!.toUpperCase())
    if (side === 'package' && d.package_value?.toUpperCase() === u && d.artwork_value)
      return artworkItems.findIndex(x => x.toUpperCase() === d.artwork_value!.toUpperCase())
  }
  return -1
}

const STATUS_NOTE: Partial<Record<RowStatus, { full: string; short: string }>> = {
  missing: { full: 'no en embalaje',  short: 'ausente'  },
  extra:   { full: 'no en artwork',   short: 'extra'    },
  order:   { full: 'orden alterado',  short: 'orden ↕'  },
  ocr:     { full: 'revisar lectura', short: 'revisar'  },
}

interface ItemRowProps {
  index:      number
  text:       string
  status:     RowStatus
  side:       'artwork' | 'package'
  orderPos?:  number
  matchedPos?: number
}

function ItemRow({ index, text, status, side, orderPos, matchedPos }: ItemRowProps) {
  const note = STATUS_NOTE[status]
  const isIssue  = status === 'missing' || status === 'extra' || status === 'ocr'

  const otherLabel = side === 'artwork' ? 'embalaje' : 'artwork'

  // Posición en la otra lista: para orden alterado (orderPos) y para ok (matchedPos).
  const otherPos = status === 'order' && orderPos  !== undefined && orderPos  >= 0 ? orderPos
                 : status === 'ok'    && matchedPos !== undefined && matchedPos >= 0 ? matchedPos
                 : undefined
  const posNote  = otherPos !== undefined ? `${otherLabel} #${otherPos + 1}` : ''

  return (
    <li className={`flex items-baseline gap-2 px-2 py-1.5 rounded text-xs ${isIssue ? 'bg-stone-100' : ''}`}>
      <span className="shrink-0 w-5 text-right font-mono tabular-nums text-stone-300 select-none">{index + 1}</span>
      <span className={`flex-1 font-mono leading-relaxed break-words min-w-0 ${isIssue ? 'text-stone-700' : 'text-stone-800'}`}>
        {text}
      </span>
      {posNote ? (
        <span className={`shrink-0 text-[10px] tabular-nums ${isIssue ? 'text-stone-400' : 'text-stone-300'}`}>
          {posNote}
        </span>
      ) : note && (
        <span className="shrink-0 text-stone-400 italic text-[10px]">
          <span className="hidden sm:inline">{note.full}</span>
          <span className="sm:hidden">{note.short}</span>
        </span>
      )}
    </li>
  )
}

// Nota regulatoria según zona
const ZONE_NOTE: Record<string, string> = {
  ingredients: 'La normativa exige orden decreciente por concentración (Art. 19.1.g EU 1223/2009). Las alteraciones de orden son incumplimientos regulatorios.',
  may_contain: 'El orden de los colorantes opcionales [(+/-)] no está regulado. Solo se verifica su presencia.',
}

export function IngredientDiff({ artworkItems, packageItems, discrepancies, zone }: Props) {
  const nMissing = discrepancies.filter(d => d.diff_type === 'falta_en_foto').length
  const nExtra   = discrepancies.filter(d => d.diff_type === 'sobra_en_foto').length
  const nOrder   = discrepancies.filter(d => d.diff_type === 'orden_alterado').length
  const ocrDiffs = discrepancies.filter(d => d.diff_type === 'posible_error_lectura')
  const hasDiffs = nMissing + nExtra + nOrder > 0

  return (
    <div className="space-y-4">
      {/* Resumen numérico */}
      <div className="flex flex-wrap items-center justify-center sm:justify-start gap-x-4 gap-y-1 text-xs text-stone-500">
        <span>{artworkItems.length} en artwork · {packageItems.length} en embalaje</span>
        {hasDiffs && (
          <span className="text-stone-700 font-medium">
            {[
              nMissing > 0 && `${nMissing} no encontrado${nMissing > 1 ? 's' : ''}`,
              nExtra   > 0 && `${nExtra} adicional${nExtra > 1 ? 'es' : ''}`,
              nOrder   > 0 && `${nOrder} orden alterado`,
            ].filter(Boolean).join(' · ')}
          </span>
        )}
        {!hasDiffs && ocrDiffs.length === 0 && (
          <span className="text-stone-700 font-medium">Sin diferencias</span>
        )}
      </div>

      {/* Listas comparadas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-3">
        {(['artwork', 'package'] as const).map(side => {
          const items = side === 'artwork' ? artworkItems : packageItems
          const title = side === 'artwork' ? 'Artwork aprobado' : 'Embalaje físico'
          return (
            <div key={side}>
              <p className="text-[11px] font-semibold text-stone-400 uppercase tracking-widest mb-1.5 text-center sm:text-left">{title}</p>
              <ol className="space-y-px max-h-[480px] overflow-y-auto">
                {items.length === 0
                  ? <li className="text-xs text-stone-300 px-2 py-2">Sin datos extraídos</li>
                  : items.map((item, i) => {
                      const status     = getStatus(item, side, discrepancies)
                      const otherItems = side === 'artwork' ? packageItems : artworkItems
                      const orderPos   = status === 'order'
                        ? getOrderPosition(item, side, artworkItems, packageItems, discrepancies)
                        : undefined
                      const matchedPos = status === 'ok'
                        ? otherItems.findIndex(x => x.toUpperCase() === item.toUpperCase())
                        : undefined
                      return <ItemRow key={i} index={i} text={item} status={status} side={side} orderPos={orderPos} matchedPos={matchedPos} />
                    })
                }
              </ol>
            </div>
          )
        })}
      </div>

      {/* Nota regulatoria */}
      {ZONE_NOTE[zone] && (
        <p className="text-[11px] text-stone-400 border-t border-stone-100 pt-3">
          {ZONE_NOTE[zone]}
        </p>
      )}

      {/* Coincidencias aproximadas OCR */}
      {ocrDiffs.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-stone-500">
            {ocrDiffs.length} coincidencia{ocrDiffs.length > 1 ? 's' : ''} aproximada{ocrDiffs.length > 1 ? 's' : ''} — posible error de lectura óptica
          </p>
          {ocrDiffs.map((d, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 text-xs font-mono bg-stone-50 border border-stone-200 rounded px-3 py-2">
              <div>
                <span className="text-[10px] font-sans text-stone-400 block mb-0.5">Artwork</span>
                <span className="text-stone-800">{d.artwork_value}</span>
              </div>
              <div>
                <span className="text-[10px] font-sans text-stone-400 block mb-0.5">Embalaje</span>
                <span className="text-stone-700">{d.package_value}</span>
                {d.similarity_score != null && (
                  <span className="ml-2 text-stone-400 font-sans tabular-nums text-[10px]">
                    {Math.round(d.similarity_score * 100)}% similitud
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
