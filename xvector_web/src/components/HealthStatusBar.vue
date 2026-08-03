<template>
  <div class="page-card health">
    <div class="page-toolbar" style="margin-bottom: 0">
      <div>
        <strong>{{ t('health.title') }}</strong>
      </div>
      <a-button size="small" @click="load" :loading="loading">{{ t('app.refresh') }}</a-button>
    </div>
    <div class="items">
      <a-tag :color="healthOk ? 'success' : 'error'">
        {{ t('health.healthz') }}: {{ healthOk ? t('health.ok') : t('health.bad') }}
        <span v-if="health?.role" class="mono"> ({{ health.role }})</span>
      </a-tag>
      <a-tag :color="readyOk ? 'success' : 'error'">
        {{ t('health.readyz') }}: {{ readyOk ? t('health.ok') : t('health.bad') }}
        <span v-if="ready?.role" class="mono"> ({{ ready.role }})</span>
      </a-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchHealthz, fetchReadyz } from '@/api/system'
import type { HealthStatus } from '@/types/api'

const { t } = useI18n()
const health = ref<HealthStatus | null>(null)
const ready = ref<HealthStatus | null>(null)
const loading = ref(false)

const healthOk = computed(() => health.value?.status === 'ok')
const readyOk = computed(() => ready.value?.status === 'ok')

async function load() {
  loading.value = true
  try {
    const [h, r] = await Promise.allSettled([fetchHealthz(), fetchReadyz()])
    health.value = h.status === 'fulfilled' ? h.value : { status: 'error' }
    ready.value = r.status === 'fulfilled' ? r.value : { status: 'error' }
  } finally {
    loading.value = false
  }
}

onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.health {
  margin-bottom: 16px;
}
.items {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
</style>
