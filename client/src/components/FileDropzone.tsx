import { useRef, useState } from 'react'
import { Upload, X, FileText, Image } from 'lucide-react'

interface Props {
  label:     string
  accept:    string
  multiple?: boolean
  maxFiles?: number
  files:     File[]
  onChange:  (files: File[]) => void
  hint?:     string
}

export function FileDropzone({ label, accept, multiple = false, maxFiles = 1, files, onChange, hint }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return
    onChange([...files, ...Array.from(incoming)].slice(0, maxFiles))
  }

  const removeFile = (index: number) => onChange(files.filter((_, i) => i !== index))

  const isPdf = accept.includes('pdf')

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-stone-700">{label}</label>

      {files.length < maxFiles && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            addFiles(e.dataTransfer.files)
          }}
          className={`border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer transition-colors select-none ${
            dragging
              ? 'border-stone-500 bg-stone-100'
              : 'border-stone-300 bg-white hover:border-stone-400 hover:bg-stone-50'
          }`}
        >
          <Upload className="w-6 h-6 text-stone-400 mb-2.5" strokeWidth={1.5} />
          <p className="text-sm text-stone-600 text-center">
            Arrastra o <span className="font-medium text-stone-900 underline underline-offset-2">selecciona</span>
          </p>
          {hint && <p className="text-xs text-stone-400 mt-1 text-center">{hint}</p>}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept={accept}
            multiple={multiple && maxFiles > 1}
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>
      )}

      {files.length > 0 && (
        <ul className="space-y-1.5">
          {files.map((file, i) => (
            <li key={i} className="flex items-center gap-2.5 bg-white border border-stone-200 rounded-lg px-3 py-2.5">
              {isPdf
                ? <FileText className="w-4 h-4 text-stone-400 shrink-0" strokeWidth={1.5} />
                : <Image    className="w-4 h-4 text-stone-400 shrink-0" strokeWidth={1.5} />
              }
              <span className="text-sm text-stone-700 truncate flex-1 font-medium">{file.name}</span>
              <span className="text-xs text-stone-400 shrink-0 tabular-nums">{(file.size / 1024).toFixed(0)} KB</span>
              <button
                type="button"
                onClick={() => removeFile(i)}
                className="text-stone-400 hover:text-stone-700 transition-colors shrink-0 ml-1"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
