<template>
  <div class="backtest-page">
    <van-nav-bar title="📊 策略回测" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="replay" @click="loadStrategies" style="padding:4px" />
      </template>
    </van-nav-bar>

    <!-- 策略选择 -->
    <van-cell-group title="回测策略">
      <van-radio-group v-model="selectedStrategy">
        <van-cell-group>
          <van-cell
            v-for="s in strategies"
            :key="s.key"
            :title="s.name"
            :label="s.desc"
            clickable
            @click="selectedStrategy = s.key"
          >
            <template #right-icon>
              <van-radio :name="s.key" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </van-cell-group>

    <!-- 参数配置 -->
    <van-cell-group title="回测参数">
      <van-field
        v-model="params.symbol"
        label="股票代码"
        placeholder="如 000001"
        clearable
      />
      <van-field
        v-model="params.startDate"
        label="开始日期"
        placeholder="如 2024-01-01"
        clearable
      />
      <van-field
        v-model="params.endDate"
        label="结束日期"
        placeholder="如 2024-12-31"
        clearable
      />
      <van-field
        v-model="params.initialCapital"
        label="初始资金(万)"
        type="number"
        placeholder="如 10"
        clearable
      />
    </van-cell-group>

    <!-- 操作按钮 -->
    <div class="action-area">
      <van-button type="primary" block :loading="running" @click="runBacktest">
        {{ running ? '回测执行中...' : '🚀 开始回测' }}
      </van-button>
    </div>

    <!-- 回测结果 -->
    <div class="result-area" v-if="result">
      <van-cell-group title="📈 回测结果">
        <van-cell title="策略" :value="result.strategy_name" />
        <van-cell title="股票" :value="result.symbol" />
        <van-cell title="周期" :value="result.period" />
        <van-cell title="总收益率">
          <template #value>
            <span :style="{color: result.total_return >= 0 ? '#ee0a24' : '#07c160'}">
              {{ result.total_return >= 0 ? '+' : '' }}{{ result.total_return?.toFixed(2) }}%
            </span>
          </template>
        </van-cell>
        <van-cell title="年化收益率" :value="result.annual_return?.toFixed(2) + '%'" />
        <van-cell title="最大回撤" :value="result.max_drawdown?.toFixed(2) + '%'" />
        <van-cell title="交易次数" :value="result.trade_count" />
        <van-cell title="胜率" :value="result.win_rate?.toFixed(1) + '%'" />
        <van-cell title="夏普比率" :value="result.sharpe_ratio?.toFixed(2)" />
      </van-cell-group>

      <!-- 交易明细 -->
      <van-cell-group title="📋 交易明细" v-if="result.trades?.length">
        <van-cell
          v-for="(t, i) in result.trades"
          :key="i"
        >
          <template #title>
            <van-tag :type="t.type === 'buy' ? 'danger' : 'success'" size="medium">
              {{ t.type === 'buy' ? '买入' : '卖出' }}
            </van-tag>
            <span style="margin-left:8px">{{ t.date }}</span>
          </template>
          <template #label>
            价格: {{ t.price?.toFixed(2) }} |
            数量: {{ t.quantity }} |
            {{ t.type === 'sell' ? '盈利: ' + t.profit?.toFixed(2) : '' }}
          </template>
        </van-cell>
      </van-cell-group>

      <!-- 净值曲线 -->
      <div class="equity-chart" ref="chartRef" v-if="result.equity_curve?.length">
        <div class="chart-title">净值曲线</div>
        <div class="chart-container" ref="equityChartRef" style="height: 300px"></div>
      </div>
    </div>

    <!-- 历史回测记录 -->
    <div class="history-area" v-if="history.length">
      <van-cell-group title="🕐 历史回测">
        <van-cell
          v-for="h in history"
          :key="h.id"
          :title="h.strategy_name"
          :label="h.symbol + ' · ' + h.date"
          is-link
          @click="loadHistoryResult(h.id)"
        >
          <template #value>
            <span :style="{color: h.total_return >= 0 ? '#ee0a24' : '#07c160'}">
              {{ h.total_return >= 0 ? '+' : '' }}{{ h.total_return?.toFixed(1) }}%
            </span>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <van-empty v-if="!loading && !result && !strategies.length" description="暂无回测数据" />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { showToast, showLoadingToast, closeToast } from 'vant'
import { getBacktestStrategies, runBacktest as apiRunBacktest, getBacktestResults } from '../utils/api.js'

const strategies = ref([])
const selectedStrategy = ref('')
const running = ref(false)
const loading = ref(false)
const result = ref(null)
const history = ref([])
const chartRef = ref(null)
const equityChartRef = ref(null)
let equityChart = null

const params = ref({
  symbol: '000001',
  startDate: '2024-01-01',
  endDate: '2024-12-31',
  initialCapital: '10',
})

async function loadStrategies() {
  try {
    const res = await getBacktestStrategies()
    if (res.data?.status === 'ok') {
      strategies.value = res.data.data || res.data.strategies || []
      if (strategies.value.length && !selectedStrategy.value) {
        selectedStrategy.value = strategies.value[0].key
      }
    }
  } catch (e) {
    console.error('加载策略失败:', e)
  }
}

async function runBacktest() {
  if (!selectedStrategy.value) {
    showToast({ message: '请选择策略', type: 'fail' })
    return
  }
  if (!params.value.symbol) {
    showToast({ message: '请输入股票代码', type: 'fail' })
    return
  }

  running.value = true
  showLoadingToast({ message: '回测执行中...', duration: 0 })
  try {
    const res = await apiRunBacktest({
      strategy: selectedStrategy.value,
      symbol: params.value.symbol,
      start_date: params.value.startDate,
      end_date: params.value.endDate,
      initial_capital: parseFloat(params.value.initialCapital) * 10000 || 100000,
    })
    if (res.data?.status === 'ok') {
      result.value = res.data.data
      showToast('✅ 回测完成')
      await nextTick()
      renderEquityChart()
      loadHistory()
    } else {
      showToast({ message: res.data?.message || '回测失败', type: 'fail' })
    }
  } catch (e) {
    showToast({ message: '回测失败: ' + e.message, type: 'fail' })
  } finally {
    running.value = false
    closeToast()
  }
}

async function loadHistory() {
  try {
    const res = await getBacktestResults()
    if (res.data?.status === 'ok') {
      history.value = res.data.data || res.data.results || []
    }
  } catch {}
}

async function loadHistoryResult(id) {
  try {
    const res = await getBacktestResults({ id })
    if (res.data?.status === 'ok') {
      result.value = res.data.data
      await nextTick()
      renderEquityChart()
    }
  } catch {}
}

function renderEquityChart() {
  if (!equityChartRef.value || !result.value?.equity_curve?.length) return

  import('lightweight-charts').then(LW => {
    const lw = LW.default || LW
    if (equityChart) { equityChart.remove(); equityChart = null }

    const { createChart, ColorType, LineSeries } = lw
    equityChart = createChart(equityChartRef.value, {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      rightPriceScale: { borderColor: '#e0e0e0' },
      timeScale: { borderColor: '#e0e0e0', timeVisible: true },
      width: equityChartRef.value.clientWidth,
      height: 300,
    })

    const lineSeries = equityChart.addSeries(LineSeries, {
      color: '#1890ff',
      lineWidth: 2,
    })

    const data = result.value.equity_curve.map(d => ({
      time: d.date.slice(0, 10),
      value: d.value,
    }))
    lineSeries.setData(data)
    equityChart.timeScale().fitContent()
  })
}

onMounted(() => {
  loadStrategies()
  loadHistory()
})
</script>

<style scoped>
.action-area {
  padding: 12px 16px;
}
.result-area {
  margin-top: 8px;
  margin-bottom: 16px;
}
.history-area {
  margin-top: 8px;
  margin-bottom: 16px;
}
.equity-chart {
  margin-top: 8px;
  background: #fff;
}
.chart-title {
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #f0f0f0;
}
.chart-container {
  width: 100%;
}
</style>
