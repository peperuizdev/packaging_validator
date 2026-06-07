import type { ValidationReport } from './types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Provider = 'claude' | 'gemini' | 'openai'

export async function validate(
  artwork: File,
  photos: File[],
  provider: Provider = 'claude',
): Promise<ValidationReport> {
  const formData = new FormData()
  formData.append('artwork', artwork)
  for (const photo of photos) {
    formData.append('photos', photo)
  }

  const response = await fetch(`${BASE_URL}/api/validate?provider=${provider}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? `Error del servidor (${response.status})`
    throw new Error(detail)
  }

  return response.json() as Promise<ValidationReport>
}
