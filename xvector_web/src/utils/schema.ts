import type { CollectionDescribe, SchemaField } from '@/types/api'

export function fieldName(f: SchemaField): string {
  return String(f.name || f.fieldName || '')
}

export function fieldType(f: SchemaField): string {
  return String(f.dataType || f.type || f.data_type || '')
}

export function isPrimary(f: SchemaField): boolean {
  return Boolean(
    f.isPrimaryKey ||
      f.isPrimary ||
      f.is_primary_key ||
      f.is_primary,
  )
}

export function getPrimaryField(desc?: CollectionDescribe | null): SchemaField | null {
  const fields = desc?.schema?.fields || []
  const marked = fields.find(isPrimary)
  if (marked) return marked
  const hinted = String(desc?.primaryField || desc?.primary_field || '')
  if (hinted) {
    const byName = fields.find((f) => fieldName(f) === hinted)
    if (byName) return byName
  }
  return null
}

export function getVectorFields(desc?: CollectionDescribe | null): SchemaField[] {
  const fields = desc?.schema?.fields || []
  return fields.filter((f) => /vector/i.test(fieldType(f)))
}

/** All schema field names in declare order (for query outputFields). */
export function schemaFieldNames(desc?: CollectionDescribe | null): string[] {
  const fields = desc?.schema?.fields || []
  const names: string[] = []
  for (const f of fields) {
    const n = fieldName(f)
    if (n && !names.includes(n)) names.push(n)
  }
  const pk = getPrimaryField(desc)
  if (pk) {
    const n = fieldName(pk)
    if (n && !names.includes(n)) names.unshift(n)
  }
  return names
}

export function isNumericPk(f: SchemaField | null): boolean {
  if (!f) return false
  return /int|float|double/i.test(fieldType(f))
}

export function formatCell(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function buildCursorFilter(
  pk: SchemaField,
  lastPk: unknown | null,
  mode: 'first' | 'next',
): string {
  const name = fieldName(pk)
  const numeric = isNumericPk(pk)
  // First page: omit filter. zvec Doc.id is not a SQL schema field unless the
  // server mirrored the PK into scalar fields; ``id != ""`` is invalid either way.
  if (mode === 'first' || lastPk == null) {
    return ''
  }
  if (numeric) {
    return `${name} > ${lastPk}`
  }
  const escaped = String(lastPk).replace(/\\/g, '\\\\').replace(/'/g, "''")
  return `${name} > '${escaped}'`
}
