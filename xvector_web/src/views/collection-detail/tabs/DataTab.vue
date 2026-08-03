<template>
  <div>
    <a-alert
      v-if="!isLoaded"
      type="warning"
      show-icon
      :message="t('data.needLoad')"
      style="margin-bottom: 12px"
    />
    <div class="page-toolbar">
      <a-space wrap>
        <span v-if="rowCount != null">{{ t('data.approxRows', { count: rowCount }) }}</span>
        <span>{{ t('data.pageSize') }}</span>
        <a-select
          v-model:value="pageSize"
          style="width: 90px"
          :options="pageSizeOptions"
          @change="onPageSizeChange"
        />
        <a-button @click="onRefresh" :loading="loading" :disabled="!isLoaded">
          {{ t('app.refresh') }}
        </a-button>
      </a-space>
      <a-space wrap>
        <a-button type="primary" @click="openWrite('insert')" :disabled="!isLoaded">
          {{ t('data.insert') }}
        </a-button>
        <a-button @click="openWrite('upsert')" :disabled="!isLoaded">
          {{ t('data.upsert') }}
        </a-button>
        <a-button danger :disabled="!selectedRowKeys.length || !isLoaded" @click="onDelete">
          {{ t('data.delete') }}
        </a-button>
      </a-space>
    </div>

    <a-alert
      v-if="!pk"
      type="info"
      show-icon
      :message="t('data.noPk')"
      style="margin-bottom: 12px"
    />

    <a-table
      :data-source="rows"
      :columns="columns"
      :loading="loading"
      row-key="__rowKey"
      :row-selection="rowSelection"
      :pagination="false"
      size="small"
      :scroll="{ x: true }"
    >
      <template #bodyCell="{ column, text }">
        <template v-if="column.key !== '__actions'">
          <span class="mono truncate-cell" :title="formatCell(text)">{{ formatCell(text) }}</span>
        </template>
      </template>
    </a-table>

    <div class="pager">
      <a-button :disabled="!canPrev || loading" @click="prevPage">{{ t('app.prev') }}</a-button>
      <a-button :disabled="!canNext || loading" @click="nextPage">{{ t('app.next') }}</a-button>
    </div>

    <a-modal
      v-model:open="writeOpen"
      :title="writeMode === 'insert' ? t('data.insert') : t('data.upsert')"
      width="720px"
      :confirm-loading="writing"
      @ok="onWrite"
    >
      <p>{{ t('data.jsonHint') }}</p>
      <a-textarea v-model:value="writeJson" :rows="14" class="mono" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import {
  deleteEntities,
  insertEntities,
  queryEntities,
  upsertEntities,
} from '@/api/entities'
import { getCollectionStats, loadCollection } from '@/api/collections'
import type { CollectionDescribe, EntityRow } from '@/types/api'
import {
  buildCursorFilter,
  fieldName,
  formatCell,
  getPrimaryField,
  schemaFieldNames,
} from '@/utils/schema'

const props = defineProps<{
  dbName: string
  collectionName: string
  describe: CollectionDescribe | null
  loadState: string
}>()

const emit = defineEmits<{ loaded: [] }>()
const { t } = useI18n()

const loading = ref(false)
const rows = ref<(EntityRow & { __rowKey: string })[]>([])
const pageSize = ref(20)
const pageSizeOptions = [10, 20, 50, 100].map((v) => ({ value: v, label: String(v) }))
const historyStack = ref<unknown[]>([])
const pageStartPk = ref<unknown | null>(null)
const selectedRowKeys = ref<string[]>([])
const selectedRows = ref<EntityRow[]>([])
const rowCount = ref<number | null>(null)

const writeOpen = ref(false)
const writeMode = ref<'insert' | 'upsert'>('insert')
const writeJson = ref('[]')
const writing = ref(false)

const pk = computed(() => getPrimaryField(props.describe))
const pkName = computed(() => (pk.value ? fieldName(pk.value) : ''))
const isLoaded = computed(
  () =>
    /LoadStateLoaded/i.test(props.loadState || '') ||
    /^loaded$/i.test(props.loadState || ''),
)
const canPrev = computed(() => historyStack.value.length > 0)
const canNext = computed(() => rows.value.length >= pageSize.value && Boolean(pk.value))

const columns = computed(() => {
  const schemaNames = schemaFieldNames(props.describe)
  const keys = new Set<string>(schemaNames)
  for (const r of rows.value) {
    Object.keys(r).forEach((k) => {
      if (k !== '__rowKey') keys.add(k)
    })
  }
  // Prefer schema declare order, then any extra response keys.
  const ordered = [
    ...schemaNames.filter((k) => keys.has(k)),
    ...[...keys].filter((k) => !schemaNames.includes(k)),
  ]
  return ordered.map((k) => ({ title: k, dataIndex: k, key: k }))
})

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: (string | number)[], selected: EntityRow[]) => {
    selectedRowKeys.value = keys.map(String)
    selectedRows.value = selected
  },
}))

async function fetchPage(mode: 'first' | 'next' | 'prev', cursor: unknown | null) {
  if (!isLoaded.value) {
    rows.value = []
    message.warning(t('data.needLoad'))
    return
  }
  if (!pk.value) {
    rows.value = []
    message.warning(t('data.noPk'))
    return
  }
  loading.value = true
  try {
    const filter = buildCursorFilter(pk.value, cursor, mode === 'first' ? 'first' : 'next')
    const outputFields = schemaFieldNames(props.describe)
    const body: Record<string, unknown> = {
      collectionName: props.collectionName,
      dbName: props.dbName,
      limit: pageSize.value,
    }
    if (filter) body.filter = filter
    if (outputFields.length) body.outputFields = outputFields
    const data = (await queryEntities(body, true)) || []
    rows.value = data.map((r, i) => ({
      ...r,
      __rowKey: `${r[pkName.value] ?? i}-${i}`,
    }))
    pageStartPk.value = cursor
    selectedRowKeys.value = []
    selectedRows.value = []
    const st = await getCollectionStats(props.collectionName, props.dbName).catch(() => null)
    rowCount.value = typeof st?.rowCount === 'number' ? st.rowCount : null
  } finally {
    loading.value = false
  }
}

async function reloadFirst() {
  historyStack.value = []
  await fetchPage('first', null)
}

async function onRefresh() {
  await reloadFirst()
}

function onPageSizeChange() {
  void reloadFirst()
}

async function nextPage() {
  if (!rows.value.length || !pk.value) return
  const last = rows.value[rows.value.length - 1][pkName.value]
  historyStack.value.push(pageStartPk.value)
  await fetchPage('next', last)
}

async function prevPage() {
  if (!historyStack.value.length) return
  const prev = historyStack.value.pop()
  await fetchPage(prev == null ? 'first' : 'next', prev ?? null)
}

function openWrite(mode: 'insert' | 'upsert') {
  writeMode.value = mode
  writeJson.value = '[\n  {"id": 1, "vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]}\n]'
  writeOpen.value = true
}

async function onWrite() {
  writing.value = true
  try {
    const data = JSON.parse(writeJson.value)
    const body = {
      collectionName: props.collectionName,
      dbName: props.dbName,
      data,
    }
    if (writeMode.value === 'insert') await insertEntities(body)
    else await upsertEntities(body)
    message.success(t('app.success'))
    writeOpen.value = false
    await reloadFirst()
    emit('loaded')
  } catch (e) {
    if (e instanceof SyntaxError) message.error(String(e.message))
  } finally {
    writing.value = false
  }
}

function onDelete() {
  if (!selectedRows.value.length || !pk.value) return
  Modal.confirm({
    title: t('app.delete'),
    content: t('data.deleteConfirm', { count: selectedRows.value.length }),
    okType: 'danger',
    onOk: async () => {
      const ids = selectedRows.value.map((r) => r[pkName.value])
      await deleteEntities({
        collectionName: props.collectionName,
        dbName: props.dbName,
        ids,
      })
      message.success(t('app.success'))
      await reloadFirst()
      emit('loaded')
    },
  })
}

watch(
  () => [props.collectionName, props.loadState, Boolean(pk.value)] as const,
  () => {
    if (isLoaded.value) void reloadFirst()
  },
)

onMounted(() => {
  if (isLoaded.value) void reloadFirst()
})

async function ensureLoad() {
  await loadCollection(props.collectionName, props.dbName)
  emit('loaded')
  await reloadFirst()
}
defineExpose({ ensureLoad })
</script>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
