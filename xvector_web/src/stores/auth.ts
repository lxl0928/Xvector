import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthPayload } from '@/types/api'
import { clearAuth, loadAuth, saveAuth } from '@/utils/authStorage'
import { authLogin } from '@/api/system'

export const useAuthStore = defineStore('auth', () => {
  const auth = ref<AuthPayload | null>(loadAuth())

  const isLoggedIn = computed(() => Boolean(auth.value?.username))
  const username = computed(() => auth.value?.username || '')

  async function login(usernameInput: string, password: string) {
    const payload = { username: usernameInput.trim(), password }
    await authLogin(payload)
    saveAuth(payload)
    auth.value = payload
  }

  function logout() {
    clearAuth()
    auth.value = null
  }

  function updateLocalPassword(newPassword: string) {
    if (!auth.value) return
    const next = { ...auth.value, password: newPassword }
    saveAuth(next)
    auth.value = next
  }

  function refreshFromStorage() {
    auth.value = loadAuth()
  }

  /** Bootstrap admin from env (default username ``root``) — password is env-managed. */
  const isBootstrapAdmin = computed(
    () => (auth.value?.username || '').trim().toLowerCase() === 'root',
  )

  return {
    auth,
    isLoggedIn,
    username,
    isBootstrapAdmin,
    login,
    logout,
    updateLocalPassword,
    refreshFromStorage,
  }
})
