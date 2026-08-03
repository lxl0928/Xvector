import { createRouter, createWebHistory } from 'vue-router'
import { loadAuth } from '@/utils/authStorage'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/login/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', redirect: '/databases' },
        {
          path: 'databases',
          name: 'databases',
          component: () => import('@/views/databases/DatabaseListView.vue'),
        },
        {
          path: 'databases/:dbName',
          name: 'collections',
          component: () => import('@/views/collections/CollectionListView.vue'),
        },
        {
          path: 'databases/:dbName/collections/:collectionName',
          name: 'collection-detail',
          component: () => import('@/views/collection-detail/CollectionDetailView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const authed = Boolean(loadAuth())
  if (to.meta.public) {
    if (authed && to.path === '/login') {
      return { path: '/databases' }
    }
    return true
  }
  if (!authed) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
