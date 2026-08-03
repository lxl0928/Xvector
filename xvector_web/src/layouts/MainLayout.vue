<template>
  <a-layout class="layout">
    <a-layout-header class="header">
      <div class="brand" @click="router.push('/databases')">
        <span class="brand-mark">Xv</span>
        <div>
          <div class="brand-title">{{ t('app.title') }}</div>
          <div class="brand-sub">{{ t('app.subtitle') }}</div>
        </div>
      </div>
      <div class="header-right">
        <a-dropdown :trigger="['click']" placement="bottomRight">
          <button type="button" class="user-trigger" aria-haspopup="menu">
            <span class="user-avatar" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path
                  d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v1.2c0 .7.5 1.2 1.2 1.2h16.8c.7 0 1.2-.5 1.2-1.2v-1.2c0-3.2-6.4-4.8-9.6-4.8z"
                />
              </svg>
            </span>
            <span class="user mono">{{ username }}</span>
            <span class="user-caret" aria-hidden="true">▾</span>
          </button>
          <template #overlay>
            <a-menu class="user-menu" @click="onMenuClick">
              <a-sub-menu key="language" :title="t('app.language')">
                <a-menu-item key="lang-zh-CN">
                  <span class="lang-item">
                    <span>{{ t('app.languageZh') }}</span>
                    <span v-if="locale === 'zh-CN'" class="lang-check">✓</span>
                  </span>
                </a-menu-item>
                <a-menu-item key="lang-en-US">
                  <span class="lang-item">
                    <span>{{ t('app.languageEn') }}</span>
                    <span v-if="locale === 'en-US'" class="lang-check">✓</span>
                  </span>
                </a-menu-item>
              </a-sub-menu>

              <a-menu-item key="password" :disabled="isBootstrapAdmin">
                <a-tooltip
                  :title="isBootstrapAdmin ? t('app.changePasswordDisabled') : undefined"
                  placement="left"
                >
                  <span :class="{ 'pwd-tip-target': isBootstrapAdmin }">
                    {{ t('app.changePassword') }}
                  </span>
                </a-tooltip>
              </a-menu-item>

              <a-menu-divider />
              <a-menu-item key="logout">{{ t('app.logout') }}</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </a-layout-header>
    <a-layout-content class="content">
      <router-view />
    </a-layout-content>

    <a-modal
      v-model:open="pwdOpen"
      :title="t('app.changePassword')"
      :confirm-loading="pwdSaving"
      destroy-on-close
      @ok="onSavePassword"
    >
      <a-form layout="vertical" class="pwd-form">
        <a-form-item :label="t('app.oldPassword')" required>
          <a-input-password v-model:value="pwdForm.oldPassword" autocomplete="current-password" />
        </a-form-item>
        <a-form-item :label="t('app.newPassword')" required>
          <a-input-password v-model:value="pwdForm.newPassword" autocomplete="new-password" />
        </a-form-item>
        <a-form-item :label="t('app.confirmPassword')" required>
          <a-input-password v-model:value="pwdForm.confirmPassword" autocomplete="new-password" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { MenuProps } from 'ant-design-vue'
import { updatePassword } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const { username } = storeToRefs(authStore)
const { locale } = storeToRefs(appStore)

/** Default bootstrap admin username is ``root`` (XVECTOR_USERNAME). */
const isBootstrapAdmin = computed(() => username.value.trim().toLowerCase() === 'root')

const pwdOpen = ref(false)
const pwdSaving = ref(false)
const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const onMenuClick: MenuProps['onClick'] = ({ key }) => {
  const k = String(key)
  if (k === 'password') {
    if (isBootstrapAdmin.value) {
      message.info(t('app.changePasswordDisabled'))
      return
    }
    pwdForm.oldPassword = ''
    pwdForm.newPassword = ''
    pwdForm.confirmPassword = ''
    pwdOpen.value = true
    return
  }
  if (k === 'lang-zh-CN') {
    appStore.setLocale('zh-CN')
    return
  }
  if (k === 'lang-en-US') {
    appStore.setLocale('en-US')
    return
  }
  if (k === 'logout') {
    authStore.logout()
    router.replace('/login')
  }
}

async function onSavePassword() {
  if (isBootstrapAdmin.value) {
    message.info(t('app.changePasswordDisabled'))
    return Promise.reject()
  }
  if (!pwdForm.oldPassword || !pwdForm.newPassword || !pwdForm.confirmPassword) {
    message.warning(t('app.passwordRequired'))
    return Promise.reject()
  }
  if (pwdForm.newPassword !== pwdForm.confirmPassword) {
    message.warning(t('app.passwordMismatch'))
    return Promise.reject()
  }
  pwdSaving.value = true
  try {
    await updatePassword({
      userName: username.value,
      password: pwdForm.oldPassword,
      newPassword: pwdForm.newPassword,
    })
    authStore.updateLocalPassword(pwdForm.newPassword)
    message.success(t('app.success'))
    pwdOpen.value = false
  } finally {
    pwdSaving.value = false
  }
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  background: transparent;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(120deg, #0f172a 0%, #1e293b 55%, #0b3b6e 100%);
  padding: 0 24px;
  height: 64px;
  line-height: 1.2;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  color: #f8fafc;
}
.brand-mark {
  display: inline-flex;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  align-items: center;
  justify-content: center;
  background: #38bdf8;
  color: #0f172a;
  font-weight: 700;
}
.brand-title {
  font-size: 16px;
  font-weight: 700;
}
.brand-sub {
  font-size: 12px;
  opacity: 0.75;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #e2e8f0;
}
.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 4px 10px 4px 4px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.35);
  color: #e2e8f0;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.user-trigger:hover {
  background: rgba(51, 65, 85, 0.55);
  border-color: rgba(148, 163, 184, 0.55);
}
.user-avatar {
  display: inline-flex;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #38bdf8, #0ea5e9);
  color: #0f172a;
  flex-shrink: 0;
}
.user {
  opacity: 0.95;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-caret {
  font-size: 10px;
  opacity: 0.7;
  line-height: 1;
}
.lang-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  min-width: 120px;
}
.lang-check {
  color: #0ea5e9;
  font-weight: 700;
}
/* Disabled menu items set pointer-events:none; re-enable on label for tooltip hover. */
.pwd-tip-target {
  display: inline-block;
  width: 100%;
  pointer-events: auto;
  cursor: not-allowed;
}
.pwd-form {
  margin-top: 8px;
}
.content {
  padding: 20px 24px 32px;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}
</style>
