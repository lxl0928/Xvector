import { getApi, postApi, http } from './http'
import type { AuthPayload, HealthStatus } from '@/types/api'

export function fetchHealthz() {
  return getApi<HealthStatus>('/healthz')
}

export function fetchReadyz() {
  return getApi<HealthStatus>('/readyz')
}

export async function authLogin(auth: AuthPayload) {
  await http.post(
    '/v2/vectordb/auth',
    {},
    {
      headers: {
        Authorization: `Bearer ${auth.username}:${auth.password}`,
      },
    },
  )
}

export function heartbeat() {
  return postApi<{ role: string; version: string }>('/v2/vectordb/heartbeat', {})
}
