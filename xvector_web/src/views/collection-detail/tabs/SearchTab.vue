<template>
  <div>
    <a-form layout="vertical" style="max-width: 880px">
      <a-form-item :label="t('searchTab.annsField')">
        <a-select v-model:value="annsField" :options="vectorFieldOptions" />
      </a-form-item>
      <a-form-item :label="t('searchTab.vector')">
        <a-textarea v-model:value="vectorText" :rows="4" class="mono" />
      </a-form-item>
      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item :label="t('searchTab.limit')">
            <a-input-number v-model:value="limit" :min="1" :max="1000" style="width: 100%" />
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item :label="t('searchTab.filter')">
            <a-input v-model:value="filter" class="mono" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item :label="t('searchTab.outputFields')">
        <a-input v-model:value="outputFields" class="mono" placeholder="id,vector" />
      </a-form-item>
      <a-form-item :label="t('searchTab.searchParams')">
        <a-input v-model:value="searchParams" class="mono" placeholder='{"ef": 64}' />
      </a-form-item>
      <a-button type="primary" :loading="loading" @click="runSearch">
        {{ t('searchTab.run') }}
      </a-button>
    </a-form>

    <h4 style="margin-top: 20px">{{ t('searchTab.results') }}</h4>
    <a-table
      :data-source="resultRows"
      :columns="columns"
      :loading="loading"
      row-key="__rowKey"
      :pagination="false"
      size="small"
      :scroll="{ x: true }"
    >
      <template #bodyCell="{ text }">
        <span class="mono truncate-cell" :title="formatCell(text)">{{ formatCell(text) }}</span>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { searchEntities } from '@/api/entities'
import type { CollectionDescribe, EntityRow } from '@/types/api'
import { fieldName, formatCell, getVectorFields } from '@/utils/schema'

const props = defineProps<{
  dbName: string
  collectionName: string
  describe: CollectionDescribe | null
}>()

/** Round to IEEE-754 binary16 (float16) precision. */
function toFloat16(value: number): number {
  const f32 = new Float32Array(1)
  const u32 = new Uint32Array(f32.buffer)
  f32[0] = value
  const x = u32[0]
  const sign = (x >>> 16) & 0x8000
  let exp = ((x >>> 23) & 0xff) - 127 + 15
  let mant = x & 0x7fffff
  let bits: number
  if (exp <= 0) {
    if (exp < -10) bits = sign
    else {
      mant = (mant | 0x800000) >>> (1 - exp)
      bits = sign | ((mant + 0x1000) >>> 13)
    }
  } else if (exp >= 31) {
    bits = sign | 0x7c00
  } else {
    bits = sign | (exp << 10) | ((mant + 0x1000) >>> 13)
  }
  // float16 bits -> float32 number
  const s = (bits & 0x8000) << 16
  let e = (bits >> 10) & 0x1f
  let m = bits & 0x3ff
  if (e === 0) {
    if (m === 0) {
      u32[0] = s
    } else {
      while (!(m & 0x400)) {
        m <<= 1
        e -= 1
      }
      e += 1
      m &= 0x3ff
      u32[0] = s | ((e + 127 - 15) << 23) | (m << 13)
    }
  } else if (e === 31) {
    u32[0] = s | 0x7f800000 | (m << 13)
  } else {
    u32[0] = s | ((e + 127 - 15) << 23) | (m << 13)
  }
  return f32[0]
}

/** Default 1024-dim query vector with float16 precision. */
function defaultFloat16Vector(dim = 1024): string {
  const arr = new Array<number>(dim)
  for (let i = 0; i < dim; i++) {
    // Deterministic values in ~[-1, 1], quantized to float16
    const raw = Math.sin(i * 0.017) * Math.cos(i * 0.031)
    arr[i] = toFloat16(raw)
  }
  return JSON.stringify(arr)
}

const { t } = useI18n()
const loading = ref(false)
const annsField = ref('vector')
const vectorText = ref(defaultFloat16Vector(1024))
const limit = ref(10)
const filter = ref('')
const outputFields = ref('')
const searchParams = ref('')
const resultRows = ref<(EntityRow & { __rowKey: string })[]>([])

const vectorFieldOptions = computed(() => {
  const fields = getVectorFields(props.describe)
  if (!fields.length) return [{ value: 'vector', label: 'vector' }]
  return fields.map((f) => ({ value: fieldName(f), label: fieldName(f) }))
})

const columns = computed(() => {
  const keys = new Set<string>()
  for (const r of resultRows.value) {
    Object.keys(r).forEach((k) => {
      if (k !== '__rowKey') keys.add(k)
    })
  }
  return [...keys].map((k) => ({ title: k, dataIndex: k, key: k }))
})

watch(
  vectorFieldOptions,
  (opts) => {
    if (opts.length && !opts.find((o) => o.value === annsField.value)) {
      annsField.value = opts[0].value
    }
  },
  { immediate: true },
)

async function runSearch() {
  loading.value = true
  try {
    const vector = JSON.parse(vectorText.value)
    const body: Record<string, unknown> = {
      collectionName: props.collectionName,
      dbName: props.dbName,
      data: Array.isArray(vector?.[0]) ? vector : [vector],
      annsField: annsField.value,
      limit: limit.value,
      refresh: true,
    }
    if (filter.value.trim()) body.filter = filter.value.trim()
    if (outputFields.value.trim()) {
      body.outputFields = outputFields.value.split(',').map((s) => s.trim()).filter(Boolean)
    }
    if (searchParams.value.trim()) {
      body.searchParams = JSON.parse(searchParams.value)
    }
    const data = (await searchEntities(body)) || []
    const flat = Array.isArray(data[0]) ? data[0] : (data as unknown as EntityRow[])
    resultRows.value = (flat || []).map((r, i) => ({
      ...r,
      __rowKey: `${r.id ?? i}-${i}`,
    }))
  } catch (e) {
    if (e instanceof SyntaxError) message.error(String(e.message))
  } finally {
    loading.value = false
  }
}
</script>
