import { postApi } from './http'

export function listPartitions(collectionName: string, dbName: string) {
  return postApi<string[] | { partitionNames?: string[] }>(
    '/v2/vectordb/partitions/list',
    { collectionName, dbName },
  )
}

export function createPartition(collectionName: string, partitionName: string, dbName: string) {
  return postApi('/v2/vectordb/partitions/create', {
    collectionName,
    partitionName,
    dbName,
  })
}

export function dropPartition(collectionName: string, partitionName: string, dbName: string) {
  return postApi('/v2/vectordb/partitions/drop', {
    collectionName,
    partitionName,
    dbName,
  })
}

export function loadPartition(collectionName: string, partitionNames: string[], dbName: string) {
  return postApi('/v2/vectordb/partitions/load', {
    collectionName,
    partitionNames,
    dbName,
  })
}

export function releasePartition(
  collectionName: string,
  partitionNames: string[],
  dbName: string,
) {
  return postApi('/v2/vectordb/partitions/release', {
    collectionName,
    partitionNames,
    dbName,
  })
}

export function getPartitionStats(
  collectionName: string,
  partitionName: string,
  dbName: string,
) {
  return postApi('/v2/vectordb/partitions/get_stats', {
    collectionName,
    partitionName,
    dbName,
  })
}
