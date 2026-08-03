<template>
  <div>
    <a-breadcrumb style="margin-bottom: 12px">
      <a-breadcrumb-item>
        <a @click="router.push('/databases')">{{ t('db.title') }}</a>
      </a-breadcrumb-item>
      <a-breadcrumb-item>
        <a class="mono" @click="router.push(`/databases/${encodeURIComponent(dbName)}`)">
          {{ dbName }}
        </a>
      </a-breadcrumb-item>
      <a-breadcrumb-item class="mono">{{ collectionName }}</a-breadcrumb-item>
    </a-breadcrumb>

    <div class="page-card" style="margin-bottom: 12px">
      <div class="page-toolbar" style="margin-bottom: 0">
        <div>
          <h2 style="margin: 0" class="mono">{{ collectionName }}</h2>
          <div style="margin-top: 8px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
            <a-badge
              :status="isLoaded ? 'success' : 'error'"
              :text="`${t('collection.loadState')}: ${loadState || '-'}`"
            />
            <a-tag color="blue">{{ t('collection.rowCount') }}: {{ rowCount ?? '-' }}</a-tag>
          </div>
        </div>
        <a-space>
          <a-button @click="refreshMeta" :loading="metaLoading">{{ t('app.refresh') }}</a-button>
          <a-button
            type="primary"
            :loading="loadActionLoading"
            @click="onToggleLoad"
          >
            {{ isLoaded ? t('collection.unload') : t('collection.load') }}
          </a-button>
        </a-space>
      </div>
    </div>

    <div class="page-card">
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="schema" :tab="t('tabs.schema')">
          <SchemaTab :describe="describe" :loading="metaLoading" />
        </a-tab-pane>
        <a-tab-pane key="data" :tab="t('tabs.data')">
          <DataTab
            :db-name="dbName"
            :collection-name="collectionName"
            :describe="describe"
            :load-state="loadState"
            @loaded="refreshMeta"
          />
        </a-tab-pane>
        <a-tab-pane key="search" :tab="t('tabs.search')">
          <SearchTab
            :db-name="dbName"
            :collection-name="collectionName"
            :describe="describe"
          />
        </a-tab-pane>
        <a-tab-pane key="partitions" :tab="t('tabs.partitions')">
          <PartitionsTab :db-name="dbName" :collection-name="collectionName" />
        </a-tab-pane>
        <a-tab-pane key="indexes" :tab="t('tabs.indexes')">
          <IndexesTab
            :db-name="dbName"
            :collection-name="collectionName"
            :describe="describe"
          />
        </a-tab-pane>
        <a-tab-pane key="aliases" :tab="t('tabs.aliases')">
          <AliasesTab :db-name="dbName" :collection-name="collectionName" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  describeCollection,
  getCollectionStats,
  getLoadState,
  loadCollection,
  releaseCollection,
} from '@/api/collections'
import type { CollectionDescribe } from '@/types/api'
import SchemaTab from './tabs/SchemaTab.vue'
import DataTab from './tabs/DataTab.vue'
import SearchTab from './tabs/SearchTab.vue'
import PartitionsTab from './tabs/PartitionsTab.vue'
import IndexesTab from './tabs/IndexesTab.vue'
import AliasesTab from './tabs/AliasesTab.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const dbName = computed(() => String(route.params.dbName || 'default'))
const collectionName = computed(() => String(route.params.collectionName || ''))

const activeTab = ref('schema')
const metaLoading = ref(false)
const loadActionLoading = ref(false)
const describe = ref<CollectionDescribe | null>(null)
const loadState = ref('')
const rowCount = ref<number | null>(null)

const isLoaded = computed(
  () =>
    /LoadStateLoaded/i.test(loadState.value || '') ||
    /^loaded$/i.test(loadState.value || ''),
)

async function refreshMeta() {
  metaLoading.value = true
  try {
    const [d, ls, st] = await Promise.all([
      describeCollection(collectionName.value, dbName.value),
      getLoadState(collectionName.value, dbName.value).catch(() => ({})),
      getCollectionStats(collectionName.value, dbName.value).catch(() => ({})),
    ])
    describe.value = d
    loadState.value = String((ls as { state?: string; loadState?: string }).state
      || (ls as { loadState?: string }).loadState
      || '')
    rowCount.value =
      typeof (st as { rowCount?: number }).rowCount === 'number'
        ? (st as { rowCount: number }).rowCount
        : null
  } finally {
    metaLoading.value = false
  }
}

async function onToggleLoad() {
  loadActionLoading.value = true
  try {
    if (isLoaded.value) {
      await releaseCollection(collectionName.value, dbName.value)
    } else {
      await loadCollection(collectionName.value, dbName.value)
    }
    message.success(t('app.success'))
    await refreshMeta()
  } finally {
    loadActionLoading.value = false
  }
}

onMounted(refreshMeta)
</script>
