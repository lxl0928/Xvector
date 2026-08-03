<template>
  <div>
    <a-spin :spinning="loading">
      <a-table
        :data-source="fields"
        :columns="columns"
        row-key="key"
        :pagination="false"
        size="small"
        style="margin-bottom: 16px"
      />
      <h4>{{ t('collection.schemaJson') }}</h4>
      <pre class="mono json">{{ pretty }}</pre>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CollectionDescribe } from '@/types/api'
import { fieldName, fieldType, isPrimary } from '@/utils/schema'

const props = defineProps<{
  describe: CollectionDescribe | null
  loading: boolean
}>()

const { t } = useI18n()

const fields = computed(() =>
  (props.describe?.schema?.fields || []).map((f, i) => ({
    key: `${fieldName(f)}-${i}`,
    name: fieldName(f),
    dataType: fieldType(f),
    isPrimaryKey: isPrimary(f),
    autoID: Boolean(f.autoID),
    dim: f.dim ?? f.dimension ?? '',
  })),
)

const columns = computed(() => [
  { title: 'name', dataIndex: 'name', key: 'name' },
  { title: 'dataType', dataIndex: 'dataType', key: 'dataType' },
  { title: 'isPrimaryKey', dataIndex: 'isPrimaryKey', key: 'isPrimaryKey' },
  { title: 'autoID', dataIndex: 'autoID', key: 'autoID' },
  { title: 'dim', dataIndex: 'dim', key: 'dim' },
])

const pretty = computed(() => JSON.stringify(props.describe, null, 2))
</script>

<style scoped>
.json {
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  max-height: 480px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
