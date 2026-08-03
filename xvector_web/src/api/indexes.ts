import { postApi } from './http'

export function listIndexes(collectionName: string, dbName: string) {
  return postApi<unknown>('/v2/vectordb/indexes/list', { collectionName, dbName })
}

export function describeIndex(collectionName: string, dbName: string, indexName?: string) {
  return postApi('/v2/vectordb/indexes/describe', {
    collectionName,
    dbName,
    indexName,
  })
}

export function createIndex(body: Record<string, unknown>) {
  return postApi('/v2/vectordb/indexes/create', body)
}

export function dropIndex(collectionName: string, indexName: string, dbName: string) {
  return postApi('/v2/vectordb/indexes/drop', { collectionName, indexName, dbName })
}
