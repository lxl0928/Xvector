import type { AuthPayload } from '@/types/api'

const AUTH_KEY = 'xvector_web_auth'
const LOCALE_KEY = 'xvector_web_locale'

export function loadAuth(): AuthPayload | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as AuthPayload
    if (!parsed?.username || parsed.password == null) return null
    return parsed
  } catch {
    return null
  }
}

export function saveAuth(auth: AuthPayload): void {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
}

export function clearAuth(): void {
  localStorage.removeItem(AUTH_KEY)
}

export function loadLocale(): 'zh-CN' | 'en-US' {
  const v = localStorage.getItem(LOCALE_KEY)
  return v === 'en-US' ? 'en-US' : 'zh-CN'
}

export function saveLocale(locale: 'zh-CN' | 'en-US'): void {
  localStorage.setItem(LOCALE_KEY, locale)
}
