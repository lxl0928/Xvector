import axios, { type AxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'
import type { ApiEnvelope } from '@/types/api'
import { clearAuth, loadAuth } from '@/utils/authStorage'
import router from '@/router'

export const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.request.use((config) => {
  const auth = loadAuth()
  if (auth) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${auth.username}:${auth.password}`
  }
  return config
})

function logoutAndRedirect() {
  clearAuth()
  if (router.currentRoute.value.path !== '/login') {
    router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  }
}

http.interceptors.response.use(
  (res) => {
    const body = res.data as ApiEnvelope | undefined
    if (body && typeof body.code === 'number' && body.code !== 0) {
      const msg = body.message || `error code ${body.code}`
      message.error(msg)
      return Promise.reject(body)
    }
    return res
  },
  (err) => {
    if (err.response?.status === 401) {
      message.error(err.response?.data?.message || 'authentication failed')
      logoutAndRedirect()
    } else {
      const msg =
        err.response?.data?.message ||
        err.message ||
        'network error'
      message.error(msg)
    }
    return Promise.reject(err)
  },
)

export async function postApi<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const res = await http.post<ApiEnvelope<T>>(url, data ?? {}, config)
  return res.data.data
}

export async function getApi<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await http.get<T>(url, config)
  return res.data
}
