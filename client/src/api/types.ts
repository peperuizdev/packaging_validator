export type Verdict = 'APROBADO' | 'REVISION_REQUERIDA'
export type Severity = 'critico' | 'medio'
export type DifferenceType =
  | 'falta_en_foto'
  | 'sobra_en_foto'
  | 'orden_alterado'
  | 'posible_error_lectura'

export interface Discrepancy {
  zone:             string
  diff_type:        DifferenceType
  artwork_value?:   string
  package_value?:   string
  note?:            string
  severity:         Severity
  similarity_score?: number
}

export interface ZoneSides {
  artwork: string[]
  package: string[]
}

export interface ChecklistItem {
  key:        string
  label:      string
  in_artwork: boolean
  in_package: boolean
}

export interface ValidationReport {
  verdict:       Verdict
  summary:       string
  narrative?:    string
  discrepancies: Discrepancy[]
  zone_values:   Record<string, ZoneSides>
  checklist:     ChecklistItem[]
}
