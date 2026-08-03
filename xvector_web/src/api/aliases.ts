import { postApi } from './http'

export function listAliases(dbName: string, collectionName?: string) {
  return postApi<unknown>('/v2/vectordb/aliases/list', {
    dbName,
    collectionName,
  })
}

export function createAlias(aliasName: string, collectionName: string, dbName: string) {
  return postApi('/v2/vectordb/aliases/create', { aliasName, collectionName, dbName })
}

export function dropAlias(aliasName: string, dbName: string) {
  return postApi('/v2/vectordb/aliases/drop', { aliasName, dbName })
}

export function alterAlias(aliasName: string, collectionName: string, dbName: string) {
  return postApi('/v2/vectordb/aliases/alter', { aliasName, collectionName, dbName })
}

export function describeAlias(aliasName: string, dbName: string) {
  return postApi('/v2/vectordb/aliases/describe', { aliasName, dbName })
}
