<template>
  <div>
    <div class="page-toolbar">
      <h4 style="margin: 0">{{ t('tabs.indexes') }}</h4>
      <a-space>
        <a-button @click="load" :loading="loading">{{ t('app.refresh') }}</a-button>
        <a-button type="primary" @click="openCreate">{{ t('app.create') }}</a-button>
      </a-space>
    </div>
    <a-table
      :data-source="rows"
      :columns="columns"
      :loading="loading"
      row-key="key"
      :pagination="false"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'actions'">
          <a-button type="link" danger size="small" @click="onDrop(record.indexName)">
            {{ t('app.delete') }}
          </a-button>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="createOpen"
      :title="t('index.createTitle')"
      :confirm-loading="creating"
      @ok="onCreate"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('index.fieldName')" required>
          <a-select v-model:value="form.fieldName" :options="fieldOptions" />
        </a-form-item>
        <a-form-item :label="t('index.indexName')">
          <a-input v-model:value="form.indexName" class="mono" />
        </a-form-item>
        <a-form-item :label="t('index.indexType')" required>
          <a-select
            v-model:value="form.indexType"
            :options="['FLAT', 'HNSW', 'IVF_FLAT'].map((v) => ({ value: v, label: v }))"
          />
        </a-form-item>
        <a-form-item :label="t('index.metricType')" required>
          <a-select
            v-model:value="form.metricType"
            :options="['L2', 'IP', 'COSINE'].map((v) => ({ value: v, label: v }))"
          />
        </a-form-item>
        <a-form-item :label="t('index.params')">
          <a-textarea v-model:value="form.params" :rows="4" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import { createIndex, describeIndex, dropIndex } from '@/api/indexes'
import type { CollectionDescribe } from '@/types/api'
import { fieldName, getVectorFields } from '@/utils/schema'

const props = defineProps<{
  dbName: string
  collectionName: string
  describe: CollectionDescribe | null
}>()

const { t } = useI18n()
const loading = ref(false)
const rawList = ref<unknown[]>([])
const createOpen = ref(false)
const creating = ref(false)
const form = reactive({
  fieldName: 'vector',
  indexName: 'vector_idx',
  indexType: 'HNSW',
  metricType: 'L2',
  params: '{"M": 16, "efConstruction": 200}',
})

const fieldOptions = computed(() => {
  const fields = getVectorFields(props.describe)
  if (!fields.length) return [{ value: 'vector', label: 'vector' }]
  return fields.map((f) => ({ value: fieldName(f), label: fieldName(f) }))
})

const rows = computed(() =>
  rawList.value.map((item, i) => {
    if (typeof item === 'string') {
      return {
        key: `${item}-${i}`,
        fieldName: '-',
        indexName: item,
        indexType: '-',
        metricType: '-',
      }
    }
    const obj = (item || {}) as Record<string, unknown>
    const indexName = String(obj.indexName || obj.name || `index-${i}`)
    return {
      key: `${indexName}-${i}`,
      fieldName: String(obj.fieldName ?? '-'),
      indexName,
      indexType: String(obj.indexType ?? '-'),
      metricType: String(obj.metricType ?? '-'),
    }
  }),
)

const columns = computed(() => [
  { title: t('index.fieldName'), dataIndex: 'fieldName', key: 'fieldName' },
  { title: t('index.indexName'), dataIndex: 'indexName', key: 'indexName' },
  { title: t('index.indexType'), dataIndex: 'indexType', key: 'indexType' },
  { title: t('index.metricType'), dataIndex: 'metricType', key: 'metricType' },
  { title: t('app.actions'), key: 'actions', width: 100 },
])

function normalizeList(data: unknown): unknown[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>
    for (const k of ['indexes', 'indexNames', 'data']) {
      if (Array.isArray(obj[k])) return obj[k] as unknown[]
    }
  }
  return data == null ? [] : [data]
}

async function load() {
  loading.value = true
  try {
    // describe（不传 indexName）返回完整索引对象；list 仅返回名称
    const data = await describeIndex(props.collectionName, props.dbName)
    rawList.value = normalizeList(data)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  if (fieldOptions.value.length) form.fieldName = fieldOptions.value[0].value
  createOpen.value = true
}

async function onCreate() {
  creating.value = true
  try {
    let params: Record<string, unknown> | undefined
    if (form.params.trim()) params = JSON.parse(form.params)
    await createIndex({
      collectionName: props.collectionName,
      dbName: props.dbName,
      fieldName: form.fieldName,
      indexName: form.indexName || undefined,
      indexType: form.indexType,
      metricType: form.metricType,
      params,
    })
    message.success(t('app.success'))
    createOpen.value = false
    await load()
  } catch (e) {
    if (e instanceof SyntaxError) message.error(String(e.message))
  } finally {
    creating.value = false
  }
}

function onDrop(name: string) {
  Modal.confirm({
    title: t('app.delete'),
    content: t('index.dropConfirm', { name }),
    okType: 'danger',
    onOk: async () => {
      await dropIndex(props.collectionName, name, props.dbName)
      message.success(t('app.success'))
      await load()
    },
  })
}

onMounted(load)
</script>
