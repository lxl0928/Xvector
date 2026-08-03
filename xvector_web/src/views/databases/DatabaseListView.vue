<template>
  <div>
    <HealthStatusBar />
    <div class="page-card">
      <div class="page-toolbar">
        <div style="display: flex; align-items: center; gap: 8px">
          <h2 style="margin: 0">{{ t('db.title') }}</h2>
          <a-tag>{{ rows.length }}</a-tag>
        </div>
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
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a class="mono" @click="goCollections(record.name)">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" size="small" @click="showDetail(record.name)">
                {{ t('app.detail') }}
              </a-button>
              <a-button type="link" size="small" @click="goCollections(record.name)">
                Collections
              </a-button>
              <a-button
                type="link"
                danger
                size="small"
                :disabled="record.name === 'default'"
                :title="record.name === 'default' ? t('db.defaultProtected') : undefined"
                @click="onDrop(record.name)"
              >
                {{ t('app.delete') }}
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="createOpen"
      :title="t('db.createTitle')"
      :confirm-loading="creating"
      @ok="onCreate"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('db.name')" required>
          <a-input v-model:value="newName" class="mono" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="detailOpen" :title="t('app.detail')" :footer="null">
      <pre class="mono detail">{{ detailText }}</pre>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import HealthStatusBar from '@/components/HealthStatusBar.vue'
import {
  createDatabase,
  describeDatabase,
  dropDatabase,
  listDatabases,
} from '@/api/databases'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const names = ref<string[]>([])
const createOpen = ref(false)
const creating = ref(false)
const newName = ref('')
const detailOpen = ref(false)
const detailText = ref('')

const rows = computed(() => names.value.map((name) => ({ name })))
const columns = computed(() => [
  { title: t('db.name'), dataIndex: 'name', key: 'name' },
  { title: t('app.actions'), key: 'actions', width: 280 },
])

async function load() {
  loading.value = true
  try {
    names.value = (await listDatabases()) || []
  } finally {
    loading.value = false
  }
}

function goCollections(dbName: string) {
  router.push(`/databases/${encodeURIComponent(dbName)}`)
}

async function showDetail(dbName: string) {
  const data = await describeDatabase(dbName)
  detailText.value = JSON.stringify(data, null, 2)
  detailOpen.value = true
}

async function onCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await createDatabase(newName.value.trim())
    message.success(t('app.success'))
    createOpen.value = false
    newName.value = ''
    await load()
  } finally {
    creating.value = false
  }
}

function onDrop(dbName: string) {
  if (dbName === 'default') {
    message.warning(t('db.defaultProtected'))
    return
  }
  Modal.confirm({
    title: t('app.delete'),
    content: t('db.dropConfirm', { name: dbName }),
    okType: 'danger',
    onOk: async () => {
      await dropDatabase(dbName)
      message.success(t('app.success'))
      await load()
    },
  })
}

onMounted(load)
</script>

<style scoped>
.detail {
  white-space: pre-wrap;
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  max-height: 420px;
  overflow: auto;
}
</style>
