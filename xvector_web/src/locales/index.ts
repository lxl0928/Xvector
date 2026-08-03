import { createI18n } from 'vue-i18n'
import { loadLocale } from '@/utils/authStorage'
import zhCN from './zh-CN'
import enUS from './en-US'

const locale = loadLocale()

export const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'en-US',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})
