import { postApi } from './http'
import type { EntityRow } from '@/types/api'

const refreshHeaders = { 'X-XVector-Refresh': 'true' }

export function queryEntities(body: Record<string, unknown>, refresh = false) {
  const { refresh: bodyRefresh, refreshSeconds: _rs, ...rest } = body
  const wantRefresh =
    refresh ||
    bodyRefresh === true ||
    bodyRefresh === 1 ||
    bodyRefresh === 'true' ||
    bodyRefresh === 'True'
  return postApi<EntityRow[]>('/v2/vectordb/entities/query', rest, {
    headers: wantRefresh ? refreshHeaders : undefined,
  })
}

export function searchEntities(body: Record<string, unknown>) {
  return postApi<EntityRow[][]>('/v2/vectordb/entities/search', body)
}

export function insertEntities(body: Record<string, unknown>) {
  return postApi('/v2/vectordb/entities/insert', body, { headers: refreshHeaders })
}

export function upsertEntities(body: Record<string, unknown>) {
  return postApi('/v2/vectordb/entities/upsert', body, { headers: refreshHeaders })
}

export function deleteEntities(body: Record<string, unknown>) {
  return postApi('/v2/vectordb/entities/delete', body, { headers: refreshHeaders })
}
