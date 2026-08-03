<template>
  <div class="login-page">
    <div class="panel">
      <div class="hero">
        <div class="logo">Xv</div>
        <h1>{{ t('app.title') }}</h1>
        <p>{{ t('app.subtitle') }}</p>
      </div>
      <a-card class="card" :bordered="false">
        <h2>{{ t('login.title') }}</h2>
        <a-form :model="formState" layout="vertical" @finish="onSubmit">
          <a-form-item
            :label="t('login.username')"
            name="username"
            :rules="[{ required: true, message: t('login.required') }]"
          >
            <a-input v-model:value="formState.username" size="large" autocomplete="username" />
          </a-form-item>
          <a-form-item
            :label="t('login.password')"
            name="password"
            :rules="[{ required: true, message: t('login.required') }]"
          >
            <a-input-password
              v-model:value="formState.password"
              size="large"
              autocomplete="current-password"
            />
          </a-form-item>
          <a-button type="primary" html-type="submit" size="large" block :loading="loading">
            {{ t('login.submit') }}
          </a-button>
        </a-form>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const formState = reactive({
  username: 'root',
  password: '',
})
const loading = ref(false)

async function onSubmit() {
  loading.value = true
  try {
    await authStore.login(formState.username, formState.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/databases'
    await router.replace(redirect)
  } catch {
    // error already toasted
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 20% 20%, rgba(56, 189, 248, 0.25), transparent 40%),
    radial-gradient(circle at 80% 0%, rgba(14, 165, 233, 0.2), transparent 35%),
    linear-gradient(160deg, #0f172a, #1e293b 50%, #0b3b6e);
  padding: 24px;
}
.panel {
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 24px;
  align-items: center;
}
.hero {
  color: #f8fafc;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #38bdf8;
  color: #0f172a;
  font-weight: 800;
  font-size: 22px;
  margin-bottom: 16px;
}
.hero h1 {
  margin: 0 0 8px;
  font-size: 40px;
}
.hero p {
  margin: 0;
  opacity: 0.8;
}
.card {
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
}
.card h2 {
  margin: 0 0 16px;
}
@media (max-width: 800px) {
  .panel {
    grid-template-columns: 1fr;
  }
}
</style>
