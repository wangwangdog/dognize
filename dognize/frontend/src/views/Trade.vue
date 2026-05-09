<template>
  <div class="trade-page">
    <van-nav-bar title="💹 实盘交易" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="replay" @click="loadAll" style="padding:4px" />
      </template>
    </van-nav-bar>

    <!-- Tab 切换 -->
    <van-tabs v-model:active="activeTab" sticky>
      <!-- 账户概况 -->
      <van-tab title="📊 概况">
        <div class="account-summary" v-if="account">
          <van-cell-group title="账户信息">
            <van-cell title="账户ID" :value="account.id || '-'" />
            <van-cell title="账户类型" :value="account.type || '-'" />
            <van-cell title="总资产">
              <template #value>
                <span class="num-large">{{ account.total_asset?.toFixed(2) || '-' }}</span>
              </template>
            </van-cell>
            <van-cell title="可用资金">
              <template #value>
                <span class="num-large" :style="{color: account.available > 0 ? '#07c160' : '#999'}">
                  {{ account.available?.toFixed(2) || '-' }}
                </span>
              </template>
            </van-cell>
            <van-cell title="持仓市值">
              <template #value>
                <span class="num-large">{{ account.market_value?.toFixed(2) || '-' }}</span>
              </template>
            </van-cell>
            <van-cell title="当日盈亏">
              <template #value>
                <span :style="{color: account.day_pnl >= 0 ? '#ee0a24' : '#07c160'}">
                  {{ account.day_pnl >= 0 ? '+' : '' }}{{ account.day_pnl?.toFixed(2) || '-' }}
                </span>
              </template>
            </van-cell>
            <van-cell title="总盈亏">
              <template #value>
                <span :style="{color: account.total_pnl >= 0 ? '#ee0a24' : '#07c160'}">
                  {{ account.total_pnl >= 0 ? '+' : '' }}{{ account.total_pnl?.toFixed(2) || '-' }}
                </span>
              </template>
            </van-cell>
          </van-cell-group>
        </div>

        <div v-else-if="!loading">
          <van-empty description="暂无账户数据" />
        </div>
      </van-tab>

      <!-- 持仓 -->
      <van-tab title="📦 持仓">
        <div class="positions-area">
          <div v-if="positions.length">
            <van-swipe-cell v-for="p in positions" :key="p.symbol">
              <van-cell :title="p.name || p.symbol" :label="p.symbol">
                <template #value>
                  <div class="pos-value">
                    <div>持仓: {{ p.quantity }}</div>
                    <div :style="{color: p.pnl >= 0 ? '#ee0a24' : '#07c160'}">
                      {{ p.pnl >= 0 ? '+' : '' }}{{ p.pnl?.toFixed(2) }}
                    </div>
                  </div>
                </template>
              </van-cell>
              <template #right>
                <van-button square type="danger" text="卖出" @click="quickSell(p)" style="height:100%" />
              </template>
            </van-swipe-cell>
          </div>
          <van-empty v-else description="暂无持仓" />
        </div>
      </van-tab>

      <!-- 下单 -->
      <van-tab title="📝 下单">
        <van-form @submit="doPlaceOrder">
          <van-cell-group title="下单">
            <van-field
              v-model="order.symbol"
              name="symbol"
              label="股票代码"
              placeholder="如 000001"
              clearable
              :rules="[{ required: true, message: '请输入股票代码' }]"
            />
            <van-field
              v-model="order.price"
              name="price"
              label="价格"
              type="number"
              placeholder="限价委托价"
              clearable
            />
            <van-field
              v-model="order.quantity"
              name="quantity"
              label="数量(股)"
              type="number"
              placeholder="买入数量"
              clearable
              :rules="[{ required: true, message: '请输入数量' }]"
            />
            <van-cell title="方向">
              <template #value>
                <van-radio-group v-model="order.side" direction="horizontal">
                  <van-radio name="buy" style="margin-right:16px">买入</van-radio>
                  <van-radio name="sell">卖出</van-radio>
                </van-radio-group>
              </template>
            </van-cell>
            <van-cell title="订单类型">
              <template #value>
                <van-radio-group v-model="order.type" direction="horizontal">
                  <van-radio name="limit" style="margin-right:16px">限价</van-radio>
                  <van-radio name="market">市价</van-radio>
                </van-radio-group>
              </template>
            </van-cell>
          </van-cell-group>

          <div style="padding: 16px">
            <van-button round block type="danger" native-type="submit" :loading="ordering">
              {{ ordering ? '提交中...' : '🚀 提交订单' }}
            </van-button>
          </div>
        </van-form>
      </van-tab>

      <!-- 订单列表 -->
      <van-tab title="📋 订单">
        <div class="orders-area">
          <van-cell-group v-if="orders.length">
            <van-cell
              v-for="o in orders"
              :key="o.id"
            >
              <template #title>
                <van-tag
                  :type="o.side === 'buy' ? 'danger' : 'success'"
                  size="medium"
                >{{ o.side === 'buy' ? '买入' : '卖出' }}</van-tag>
                <span style="margin-left:8px">{{ o.symbol }}</span>
              </template>
              <template #label>
                数量: {{ o.quantity }} | 价格: {{ o.price?.toFixed(2) }} | {{ o.date }}
              </template>
              <template #value>
                <van-tag :type="orderStatusType(o.status)">{{ o.status }}</van-tag>
              </template>
            </van-cell>
          </van-cell-group>
          <van-empty v-else description="暂无订单" />
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import {
  getTradeAccounts, getTradePositions, getTradeOrders,
  placeOrder, getTradeStatus
} from '../utils/api.js'

const activeTab = ref(0)
const loading = ref(false)
const ordering = ref(false)

const account = ref(null)
const positions = ref([])
const orders = ref([])

const order = reactive({
  symbol: '',
  price: '',
  quantity: '',
  side: 'buy',
  type: 'limit',
})

function orderStatusType(status) {
  const map = { 'filled': 'success', 'pending': 'warning', 'cancelled': 'default', 'rejected': 'danger' }
  return map[status] || 'default'
}

async function loadAccount() {
  try {
    const res = await getTradeAccounts()
    if (res.data?.status === 'ok') {
      account.value = res.data.data
    }
  } catch {}
}

async function loadPositions() {
  try {
    const res = await getTradePositions()
    if (res.data?.status === 'ok') {
      positions.value = res.data.data || res.data.positions || []
    }
  } catch {}
}

async function loadOrders() {
  try {
    const res = await getTradeOrders()
    if (res.data?.status === 'ok') {
      orders.value = res.data.data || res.data.orders || []
    }
  } catch {}
}

async function loadAll() {
  loading.value = true
  await Promise.all([loadAccount(), loadPositions(), loadOrders()])
  loading.value = false
}

async function doPlaceOrder() {
  ordering.value = true
  try {
    const res = await placeOrder({
      symbol: order.symbol,
      side: order.side,
      type: order.type,
      price: order.price ? parseFloat(order.price) : undefined,
      quantity: parseInt(order.quantity),
    })
    if (res.data?.status === 'ok') {
      showToast('✅ 订单提交成功')
      order.symbol = ''
      order.price = ''
      order.quantity = ''
      loadOrders()
    } else {
      showToast({ message: res.data?.message || '下单失败', type: 'fail' })
    }
  } catch (e) {
    showToast({ message: '下单失败: ' + e.message, type: 'fail' })
  } finally {
    ordering.value = false
  }
}

async function quickSell(pos) {
  try {
    await showConfirmDialog({ title: '卖出确认', message: `确定卖出 ${pos.name || pos.symbol} ${pos.quantity} 股？` })
    order.symbol = pos.symbol
    order.quantity = String(pos.quantity)
    order.side = 'sell'
    order.price = ''
    order.type = 'market'
    activeTab.value = 2 // 切换到下单Tab
  } catch {}
}

onMounted(() => loadAll())
</script>

<style scoped>
.account-summary {
  margin-bottom: 16px;
}
.num-large {
  font-size: 18px;
  font-weight: 700;
}
.pos-value {
  text-align: right;
  font-size: 13px;
}
.positions-area, .orders-area {
  margin-bottom: 16px;
}
</style>
