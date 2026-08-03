<template>
  <div>
    <a-breadcrumb style="margin-bottom: 12px">
      <a-breadcrumb-item><a @click="router.push('/databases')">{{ t('db.title') }}</a></a-breadcrumb-item>
      <a-breadcrumb-item class="mono">{{ dbName }}</a-breadcrumb-item>
    </a-breadcrumb>

    <div class="page-card">
      <div class="page-toolbar">
        <div style="display: flex; align-items: center; gap: 8px">
          <h2 style="margin: 0">{{ t('collection.title') }}</h2>
          <a-tag>{{ rows.length }}</a-tag>
        </div>
        <a-space>
          <a-button @click="load" :loading="loading">{{ t('app.refresh') }}</a-button>
          <a-button type="primary" @click="openCreate">{{ t('app.create') }}</a-button>
        </a-space>
      </div>

      <a-table
        :data-source="rows"
        :columns="columns"
        :loading="loading"
        row-key="name"
        :pagination="false"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a class="mono" @click="goDetail(record.name)">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'loadState'">
            <a-badge
              :status="isLoaded(record.loadState) ? 'success' : 'error'"
              :text="record.loadState || '-'"
            />
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button type="link" size="small" @click="goDetail(record.name)">
                {{ t('app.detail') }}
              </a-button>
              <a-button type="link" size="small" @click="openRename(record.name)">
                {{ t('app.rename') }}
              </a-button>
              <a-button type="link" danger size="small" @click="onDrop(record.name)">
                {{ t('app.delete') }}
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="createOpen"
      :title="t('collection.createTitle')"
      width="720px"
      :confirm-loading="creating"
      @ok="onCreate"
    >
      <a-radio-group v-model:value="createMode" style="margin-bottom: 12px">
        <a-radio-button value="template">{{ t('collection.template') }}</a-radio-button>
        <a-radio-button value="json">{{ t('collection.advancedJson') }}</a-radio-button>
      </a-radio-group>
      <template v-if="createMode === 'template'">
        <a-form layout="vertical">
          <a-form-item :label="t('collection.name')" required>
            <a-input v-model:value="createName" class="mono" />
          </a-form-item>
          <a-form-item :label="t('collection.dim')" required>
            <a-input-number v-model:value="createDim" :min="1" style="width: 100%" />
          </a-form-item>
        </a-form>
      </template>
      <template v-else>
        <a-textarea v-model:value="createJson" :rows="14" class="mono" />
      </template>
    </a-modal>

    <a-modal
      v-model:open="renameOpen"
      :title="t('collection.renameTitle')"
      :confirm-loading="renaming"
      @ok="onRename"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('collection.newName')" required>
          <a-input v-model:value="renameTo" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import {
  createCollection,
  dropCollection,
  getLoadState,
  listCollections,
  renameCollection,
} from '@/api/collections'

type CollectionRow = { name: string; loadState: string }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const dbName = computed(() => String(route.params.dbName || 'default'))

const loading = ref(false)
const rows = ref<CollectionRow[]>([])
const columns = computed(() => [
  { title: t('collection.name'), dataIndex: 'name', key: 'name' },
  { title: t('collection.loadState'), dataIndex: 'loadState', key: 'loadState', width: 200 },
  { title: t('app.actions'), key: 'actions', width: 240 },
])

const createOpen = ref(false)
const creating = ref(false)
const createMode = ref<'template' | 'json'>('template')
const createName = ref('')
const createDim = ref(8)
const createJson = ref('')

const renameOpen = ref(false)
const renaming = ref(false)
const renameFrom = ref('')
const renameTo = ref('')

function parseLoadState(ls: unknown): string {
  const obj = (ls || {}) as { state?: string; loadState?: string }
  return String(obj.state || obj.loadState || '')
}

function isLoaded(state: string): boolean {
  return /LoadStateLoaded/i.test(state || '') || /^loaded$/i.test(state || '')
}

async function load() {
  loading.value = true
  try {
    const names = (await listCollections(dbName.value)) || []
    const states = await Promise.all(
      names.map((name) =>
        getLoadState(name, dbName.value)
          .then(parseLoadState)
          .catch(() => ''),
      ),
    )
    rows.value = names.map((name, i) => ({
      name,
      loadState: states[i] || '',
    }))
  } finally {
    loading.value = false
  }
}

function goDetail(name: string) {
  router.push(
    `/databases/${encodeURIComponent(dbName.value)}/collections/${encodeURIComponent(name)}`,
  )
}

function openCreate() {
  createMode.value = 'template'
  createName.value = ''
  createDim.value = 8
  createJson.value = JSON.stringify(
    {
      dbName: dbName.value,
      collectionName: 'demo',
      schema: {
        autoID: false,
        enableDynamicField: false,
        fields: [
          { name: 'id', dataType: 'Int64', isPrimaryKey: true, autoID: false },
          { name: 'vector', dataType: 'FloatVector', dim: 8 },
        ],
      },
    },
    null,
    2,
  )
  createOpen.value = true
}

async function onCreate() {
  creating.value = true
  try {
    let body: Record<string, unknown>
    if (createMode.value === 'template') {
      body = {
        dbName: dbName.value,
        collectionName: createName.value.trim(),
        schema: {
          autoID: false,
          enableDynamicField: false,
          fields: [
            { name: 'id', dataType: 'Int64', isPrimaryKey: true, autoID: false },
            { name: 'vector', dataType: 'FloatVector', dim: createDim.value },
          ],
        },
      }
    } else {
      body = JSON.parse(createJson.value)
      if (!body.dbName) body.dbName = dbName.value
    }
    await createCollection(body)
    message.success(t('app.success'))
    createOpen.value = false
    await load()
  } catch (e) {
    if (e instanceof SyntaxError) message.error(String(e.message))
  } finally {
    creating.value = false
  }
}

function openRename(name: string) {
  renameFrom.value = name
  renameTo.value = name
  renameOpen.value = true
}

async function onRename() {
  renaming.value = true
  try {
    await renameCollection(renameFrom.value, renameTo.value.trim(), dbName.value)
    message.success(t('app.success'))
    renameOpen.value = false
    await load()
  } finally {
    renaming.value = false
  }
}

function onDrop(name: string) {
  Modal.confirm({
    title: t('app.delete'),
    content: t('collection.dropConfirm', { name }),
    okType: 'danger',
    onOk: async () => {
      await dropCollection(name, dbName.value)
      message.success(t('app.success'))
      await load()
    },
  })
}

onMounted(load)
</script>
