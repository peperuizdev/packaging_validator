import { useState, useEffect, useRef } from 'react'
import { RotateCcw, Check } from 'lucide-react'
import { validate } from './api/client'
import type { Provider } from './api/client'
import type { ValidationReport } from './api/types'
import { FileDropzone } from './components/FileDropzone'
import { ValidationResult } from './components/ValidationResult'

type AppState = 'idle' | 'loading' | 'done' | 'error'

const PROVIDERS: { value: Provider; label: string; sub: string }[] = [
  { value: 'claude', label: 'Claude',  sub: 'Anthropic' },
  { value: 'gemini', label: 'Gemini',  sub: 'Google'    },
  { value: 'openai', label: 'GPT-4o',  sub: 'OpenAI'    },
]

const STEPS = [
  { label: 'Leyendo artwork PDF',         detail: 'Extrayendo ingredientes y campos regulatorios' },
  { label: 'Analizando embalaje físico',  detail: 'Reconociendo texto en las fotografías'        },
  { label: 'Comparando ingredientes',     detail: 'Validando orden y presencia de la lista INCI' },
  { label: 'Generando informe',           detail: 'Calculando discrepancias y resultado final'   },
]

// Tiempos de avance de paso (ms) — aproximación al proceso real del servidor.
const STEP_DELAYS = [7000, 7000, 2000]

// ── Indicador de progreso ─────────────────────────────────────────────────────

function StepIndicator({ activeStep }: { activeStep: number }) {
  return (
    <div className="w-full max-w-sm space-y-1 mx-auto">
      {STEPS.map((step, i) => {
        const done   = i < activeStep
        const active = i === activeStep
        return (
          <div key={i} className="flex items-start gap-3 py-2 justify-center sm:justify-start">
            {/* Dot */}
            <div className="mt-0.5 shrink-0 flex items-center justify-center w-5 h-5">
              {done ? (
                <span className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" strokeWidth={3} />
                </span>
              ) : active ? (
                <span className="relative w-3 h-3">
                  <span className="absolute inset-0 rounded-full bg-amber-600 animate-ping opacity-60" />
                  <span className="relative block w-3 h-3 rounded-full bg-amber-600" />
                </span>
              ) : (
                <span className="w-3 h-3 rounded-full border-2 border-zinc-200" />
              )}
            </div>
            {/* Label */}
            <div>
              <p className={`text-sm leading-none ${
                done    ? 'text-zinc-400 line-through decoration-zinc-300' :
                active  ? 'text-zinc-900 font-medium' :
                          'text-zinc-400'
              }`}>
                {step.label}
              </p>
              {active && (
                <p className="text-xs text-amber-700 mt-1">{step.detail}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [artwork,    setArtwork]    = useState<File[]>([])
  const [photos,     setPhotos]     = useState<File[]>([])
  const [provider,   setProvider]   = useState<Provider>('claude')
  const [state,      setState]      = useState<AppState>('idle')
  const [activeStep, setActiveStep] = useState(0)
  const [report,     setReport]     = useState<ValidationReport | null>(null)
  const [errorMsg,   setErrorMsg]   = useState('')
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])

  const canValidate = artwork.length === 1 && photos.length >= 1
  const isLoading   = state === 'loading'

  // Avanza los pasos en los tiempos aproximados al proceso real del servidor.
  useEffect(() => {
    if (state !== 'loading') return
    setActiveStep(0)
    let step = 0
    STEP_DELAYS.forEach((_delay, i) => {
      const t = setTimeout(() => {
        step = i + 1
        setActiveStep(step)
      }, STEP_DELAYS.slice(0, i + 1).reduce((a, b) => a + b, 0))
      timersRef.current.push(t)
    })
    return () => {
      timersRef.current.forEach(clearTimeout)
      timersRef.current = []
    }
  }, [state])

  const handleValidate = async () => {
    if (!canValidate || isLoading) return
    setState('loading')
    setReport(null)
    setErrorMsg('')

    try {
      const result = await validate(artwork[0], photos, provider)
      setReport(result)
      setState('done')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Error desconocido')
      setState('error')
    }
  }

  const handleReset = () => {
    setArtwork([])
    setPhotos([])
    setReport(null)
    setErrorMsg('')
    setState('idle')
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Cabecera ──────────────────────────────────────────────── */}
      <header className="bg-white border-b border-zinc-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
          <div className="min-w-0 flex items-center gap-2">
            <span className="font-semibold text-zinc-900 text-sm tracking-tight">Packging Validator</span>
            <span className="hidden sm:inline text-zinc-300 select-none">·</span>
            <span className="text-xs text-zinc-400 hidden sm:inline">EU Reg. 1223/2009</span>
          </div>
          {state === 'done' && (
            <button
              type="button"
              onClick={handleReset}
              className="shrink-0 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900 border border-zinc-200 rounded-md px-3 py-1.5 hover:bg-zinc-50 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span className="hidden sm:inline">Nueva validación</span>
              <span className="sm:hidden">Nueva</span>
            </button>
          )}
        </div>
      </header>

      {/* ── Contenido principal ────────────────────────────────────── */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-10">

        {/* Estado: formulario de carga */}
        {(state === 'idle' || state === 'error') && (
          <div className="space-y-6 sm:space-y-8">
            <div>
              <h1 className="text-lg font-semibold text-zinc-900">Validación comparativa de packaging</h1>
              <p className="text-sm text-zinc-500 mt-1">
                Compara el artwork aprobado con el embalaje físico y detecta discrepancias en los ingredientes INCI.
              </p>
            </div>

            {/* Carga de archivos */}
            <div className="bg-white border border-zinc-200 shadow-sm rounded-xl p-4 sm:p-6 space-y-5">
              <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">Documentos</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <FileDropzone
                  label="Artwork aprobado"
                  accept=".pdf,application/pdf"
                  files={artwork}
                  onChange={setArtwork}
                  hint="PDF de imprenta vectorizado"
                />
                <FileDropzone
                  label="Fotos del embalaje"
                  accept="image/*"
                  multiple
                  maxFiles={2}
                  files={photos}
                  onChange={setPhotos}
                  hint="1 o 2 fotografías del producto final"
                />
              </div>
            </div>

            {/* Selector de modelo */}
            <div className="bg-white border border-zinc-200 shadow-sm rounded-xl p-4 sm:p-6 space-y-3">
              <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">Modelo de análisis</h2>
              <div className="grid grid-cols-3 gap-2">
                {PROVIDERS.map(p => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setProvider(p.value)}
                    className={`py-2.5 px-3 rounded-lg border text-left transition-all ${
                      provider === p.value
                        ? 'border-amber-700 bg-amber-700 text-white'
                        : 'border-zinc-200 text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50'
                    }`}
                  >
                    <p className="text-sm font-semibold leading-none">{p.label}</p>
                    <p className={`text-xs mt-1 ${provider === p.value ? 'text-amber-200' : 'text-zinc-400'}`}>{p.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {state === 'error' && (
              <div className="border border-zinc-200 rounded-xl px-5 py-4">
                <p className="text-sm font-semibold text-zinc-800">Error al procesar</p>
                <p className="text-sm text-zinc-500 mt-0.5">{errorMsg}</p>
              </div>
            )}

            {/* Acción */}
            <button
              type="button"
              disabled={!canValidate}
              onClick={handleValidate}
              className={`w-full py-3 rounded-xl text-sm font-semibold transition-colors ${
                canValidate
                  ? 'bg-zinc-900 text-white hover:bg-zinc-800'
                  : 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
              }`}
            >
              {canValidate
                ? `Analizar con ${PROVIDERS.find(p => p.value === provider)?.label}`
                : 'Sube el artwork y al menos una foto para continuar'
              }
            </button>
          </div>
        )}

        {/* Estado: cargando */}
        {state === 'loading' && (
          <div className="flex flex-col items-center py-20 sm:py-32 gap-10">
            <StepIndicator activeStep={activeStep} />
            <p className="text-xs text-zinc-400 text-center">
              {PROVIDERS.find(p => p.value === provider)?.label} · {PROVIDERS.find(p => p.value === provider)?.sub}
              <span className="ml-2 hidden sm:inline">· El análisis puede tardar entre 15 y 30 segundos</span>
            </p>
          </div>
        )}

        {/* Estado: resultado */}
        {state === 'done' && report && (
          <ValidationResult report={report} provider={provider} />
        )}
      </main>
    </div>
  )
}
