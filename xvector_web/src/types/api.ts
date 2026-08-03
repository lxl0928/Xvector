export interface ApiEnvelope<T = unknown> {
  code: number
  message: string
  data: T
  requestId?: string
}

export interface AuthPayload {
  username: string
  password: string
}

export interface HealthStatus {
  status: string
  role?: string
  error?: string
}

export interface SchemaField {
  name?: string
  fieldName?: string
  dataType?: string
  type?: string
  data_type?: string
  isPrimaryKey?: boolean
  isPrimary?: boolean
  is_primary_key?: boolean
  is_primary?: boolean
  autoID?: boolean
  dim?: number
  dimension?: number
  [key: string]: unknown
}

export interface CollectionDescribe {
  collectionName: string
  dbName?: string
  schema?: {
    fields?: SchemaField[]
    autoID?: boolean
    enableDynamicField?: boolean
    [key: string]: unknown
  }
  shardsNum?: number
  consistencyLevel?: string
  indexes?: unknown[]
  autoId?: boolean
  primaryField?: string
  primary_field?: string
  [key: string]: unknown
}

export type EntityRow = Record<string, unknown>
