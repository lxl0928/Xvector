import { postApi } from './http'

export function listDatabases() {
  return postApi<string[]>('/v2/vectordb/databases/list', {})
}

export function createDatabase(dbName: string) {
  return postApi('/v2/vectordb/databases/create', { dbName })
}

export function dropDatabase(dbName: string) {
  return postApi('/v2/vectordb/databases/drop', { dbName })
}

export function describeDatabase(dbName: string) {
  return postApi<{ dbName: string; properties?: Record<string, unknown> }>(
    '/v2/vectordb/databases/describe',
    { dbName },
  )
}
