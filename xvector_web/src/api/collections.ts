import { postApi } from './http'
import type { CollectionDescribe } from '@/types/api'

export function listCollections(dbName: string) {
  return postApi<string[]>('/v2/vectordb/collections/list', { dbName })
}

export function createCollection(body: Record<string, unknown>) {
  return postApi('/v2/vectordb/collections/create', body)
}

export function dropCollection(collectionName: string, dbName: string) {
  return postApi('/v2/vectordb/collections/drop', { collectionName, dbName })
}

export function renameCollection(
  collectionName: string,
  newCollectionName: string,
  dbName: string,
) {
  return postApi('/v2/vectordb/collections/rename', {
    collectionName,
    newCollectionName,
    dbName,
  })
}

export function loadCollection(collectionName: string, dbName: string) {
  return postApi('/v2/vectordb/collections/load', { collectionName, dbName })
}

export function releaseCollection(collectionName: string, dbName: string) {
  return postApi('/v2/vectordb/collections/release', { collectionName, dbName })
}

export function describeCollection(collectionName: string, dbName: string) {
  return postApi<CollectionDescribe>('/v2/vectordb/collections/describe', {
    collectionName,
    dbName,
  })
}

export function getLoadState(collectionName: string, dbName: string) {
  return postApi<{ state?: string; loadState?: string }>(
    '/v2/vectordb/collections/get_load_state',
    { collectionName, dbName },
  )
}

export function getCollectionStats(collectionName: string, dbName: string) {
  return postApi<{ rowCount?: number }>('/v2/vectordb/collections/get_stats', {
    collectionName,
    dbName,
  })
}
