<template>
  <div>
    <div class="page-toolbar">
      <h4 style="margin: 0">{{ t('tabs.partitions') }}</h4>
      <a-space>
        <a-button @click="load" :loading="loading">{{ t('app.refresh') }}</a-button>
        <a-button type="primary" @click="createOpen = true">{{ t('app.create') }}</a-button>
      </a-space>
    </div>
    <a-table
      :data-source="rows"
      :columns="columns"
      :loading="loading"
      row-key="name"
      :pagination="false"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button type="link" size="small" @click="onLoad(record.name)">
              {{ t('collection.load') }}
            </a-button>
            <a-button type="link" size="small" @click="onRelease(record.name)">
              {{ t('collection.release') }}
            </a-button>
            <a-button type="link" danger size="small" @click="onDrop(record.name)">
              {{ t('app.delete') }}
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="createOpen"
      :title="t('partition.createTitle')"
      :confirm-loading="creating"
      @ok="onCreate"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('partition.name')" required>
          <a-input v-model:value="newName" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import {
  createPartition,
  dropPartition,
  listPartitions,
  loadPartition,
  releasePartition,
} from '@/api/partitions'

const props = defineProps<{
  dbName: string
  collectionName: string
}>()

const { t } = useI18n()
const loading = ref(false)
const names = ref<string[]>([])
const createOpen = ref(false)
const creating = ref(false)
const newName = ref('')

const rows = computed(() => names.value.map((name) => ({ name })))
const columns = computed(() => [
  { title: t('partition.name'), dataIndex: 'name', key: 'name' },
  { title: t('app.actions'), key: 'actions', width: 280 },
])

function normalizeList(data: unknown): string[] {
  if (Array.isArray(data)) return data.map(String)
  if (data && typeof data === 'object' && Array.isArray((data as { partitionNames?: string[] }).partitionNames)) {
    return ((data as { partitionNames: string[] }).partitionNames).map(String)
  }
  return []
}

async function load() {
  loading.value = true
  try {
    const data = await listPartitions(props.collectionName, props.dbName)
    names.value = normalizeList(data)
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await createPartition(props.collectionName, newName.value.trim(), props.dbName)
    message.success(t('app.success'))
    createOpen.value = false
    newName.value = ''
    await load()
  } finally {
    creating.value = false
  }
}

function onDrop(name: string) {
  Modal.confirm({
    title: t('app.delete'),
    content: t('partition.dropConfirm', { name }),
    okType: 'danger',
    onOk: async () => {
      await dropPartition(props.collectionName, name, props.dbName)
      message.success(t('app.success'))
      await load()
    },
  })
}

async function onLoad(name: string) {
  await loadPartition(props.collectionName, [name], props.dbName)
  message.success(t('app.success'))
}

async function onRelease(name: string) {
  await releasePartition(props.collectionName, [name], props.dbName)
  message.success(t('app.success'))
}

onMounted(load)
</script>
