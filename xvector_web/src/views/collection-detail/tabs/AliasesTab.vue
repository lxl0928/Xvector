<template>
  <div>
    <div class="page-toolbar">
      <h4 style="margin: 0">{{ t('tabs.aliases') }}</h4>
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
            <a-button type="link" size="small" @click="openAlter(record.name)">
              Alter
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
      :title="t('alias.createTitle')"
      :confirm-loading="creating"
      @ok="onCreate"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('alias.name')" required>
          <a-input v-model:value="newAlias" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="alterOpen"
      :title="t('alias.alterTitle')"
      :confirm-loading="altering"
      @ok="onAlter"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('collection.name')" required>
          <a-input v-model:value="alterCollection" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import { alterAlias, createAlias, dropAlias, listAliases } from '@/api/aliases'

const props = defineProps<{
  dbName: string
  collectionName: string
}>()

const { t } = useI18n()
const loading = ref(false)
const names = ref<string[]>([])
const createOpen = ref(false)
const creating = ref(false)
const newAlias = ref('')
const alterOpen = ref(false)
const altering = ref(false)
const alterName = ref('')
const alterCollection = ref('')

const rows = computed(() => names.value.map((name) => ({ name })))
const columns = computed(() => [
  { title: t('alias.name'), dataIndex: 'name', key: 'name' },
  { title: t('app.actions'), key: 'actions', width: 200 },
])

function normalizeList(data: unknown): string[] {
  if (Array.isArray(data)) {
    return data.map((item) => {
      if (typeof item === 'string') return item
      const obj = item as Record<string, unknown>
      return String(obj.aliasName || obj.name || JSON.stringify(item))
    })
  }
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>
    for (const k of ['aliases', 'aliasNames']) {
      if (Array.isArray(obj[k])) return normalizeList(obj[k])
    }
  }
  return []
}

async function load() {
  loading.value = true
  try {
    const data = await listAliases(props.dbName, props.collectionName)
    names.value = normalizeList(data)
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!newAlias.value.trim()) return
  creating.value = true
  try {
    await createAlias(newAlias.value.trim(), props.collectionName, props.dbName)
    message.success(t('app.success'))
    createOpen.value = false
    newAlias.value = ''
    await load()
  } finally {
    creating.value = false
  }
}

function openAlter(name: string) {
  alterName.value = name
  alterCollection.value = props.collectionName
  alterOpen.value = true
}

async function onAlter() {
  altering.value = true
  try {
    await alterAlias(alterName.value, alterCollection.value.trim(), props.dbName)
    message.success(t('app.success'))
    alterOpen.value = false
    await load()
  } finally {
    altering.value = false
  }
}

function onDrop(name: string) {
  Modal.confirm({
    title: t('app.delete'),
    content: t('alias.dropConfirm', { name }),
    okType: 'danger',
    onOk: async () => {
      await dropAlias(name, props.dbName)
      message.success(t('app.success'))
      await load()
    },
  })
}

onMounted(load)
</script>
