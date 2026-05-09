import { createRouter, createWebHashHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Home from '../views/Home.vue'
import Kline from '../views/Kline.vue'
import Fundamentals from '../views/Fundamentals.vue'
import Screener from '../views/Screener.vue'
import Strategies from '../views/Strategies.vue'
import Chanlun from '../views/Chanlun.vue'
import Links from '../views/Links.vue'
import Settings from '../views/Settings.vue'
// 新增页面
import Backtest from '../views/Backtest.vue'
import Trade from '../views/Trade.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/', name: 'Home', component: Home, meta: { requiresAuth: true } },
  { path: '/kline/:symbol', name: 'Kline', component: Kline, props: true, meta: { requiresAuth: true } },
  { path: '/fund/:symbol', name: 'Fund', component: Fundamentals, props: true, meta: { requiresAuth: true } },
  { path: '/screener', name: 'Screener', component: Screener, meta: { requiresAuth: true } },
  { path: '/strategies', name: 'Strategies', component: Strategies, meta: { requiresAuth: true } },
  { path: '/chanlun', name: 'Chanlun', component: Chanlun, meta: { requiresAuth: true } },
  { path: '/chanlun/:symbol', name: 'ChanlunBySymbol', component: Chanlun, props: true, meta: { requiresAuth: true } },
  { path: '/links', name: 'Links', component: Links, meta: { requiresAuth: true } },
  { path: '/backtest', name: 'Backtest', component: Backtest, meta: { requiresAuth: true } },
  { path: '/trade', name: 'Trade', component: Trade, meta: { requiresAuth: true } },
  { path: '/settings', name: 'Settings', component: Settings, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// Auth guard: check localStorage
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth) {
    const username = localStorage.getItem('username')
    if (!username) {
      next('/login')
      return
    }
  }
  next()
})

// Helper: get current username
export function getUsername() {
  return localStorage.getItem('username') || ''
}

export default router
