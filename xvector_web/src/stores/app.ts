import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loadLocale, saveLocale } from '@/utils/authStorage'
import { i18n } from '@/locales'

export const useAppStore = defineStore('app', () => {
  const locale = ref<'zh-CN' | 'en-US'>(loadLocale())

  function setLocale(next: 'zh-CN' | 'en-US') {
    locale.value = next
    saveLocale(next)
    i18n.global.locale.value = next
  }

  return { locale, setLocale }
})
