function requiredUrl(name: string, value: string | undefined): string {
  if (!value) throw new Error(`${name} is required`)
  const parsed = new URL(value)
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error(`${name} must be an HTTP(S) URL`)
  }
  return parsed.origin
}

function required(name: string, value: string | undefined): string {
  if (!value || value.startsWith('replace-with-')) throw new Error(`${name} is required`)
  return value
}

export const config = {
  apiBaseUrl: requiredUrl('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL),
  googleClientId: required('VITE_GOOGLE_CLIENT_ID', import.meta.env.VITE_GOOGLE_CLIENT_ID),
} as const

