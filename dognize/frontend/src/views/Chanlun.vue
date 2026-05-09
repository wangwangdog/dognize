<template>
  <div class="chanlun-page">
    <van-nav-bar title="📉 缠论对比" left-arrow @click-left="$router.back()">
      <template #right><van-icon name="replay" @click="doAnalyze" style="padding:4px" /></template>
    </van-nav-bar>

    <div class="search-area">
      <div class="search-row">
        <van-search v-model="symbol" placeholder="输入股票代码，如 002210"
          @search="doAnalyze" :loading="loading" clearable style="flex:1" />
        <div class="freq-switch">
          <span v-for="f in freqs" :key="f.value"
            class="freq-btn" :class="{ active: freq === f.value }"
            @click="switchFreq(f.value)">{{ f.label }}</span>
        </div>
      </div>
    </div>

    <!-- 算法切换 -->
    <div class="algo-bar" v-if="result.status === 'ok'">
      <span
        v-for="a in algorithms"
        :key="a.key"
        class="algo-btn"
        :class="{ active: activeAlgo === a.key }"
        :style="{ '--accent': a.color, borderColor: activeAlgo === a.key ? a.color : '', color: activeAlgo === a.key ? a.color : '#666', background: activeAlgo === a.key ? a.color + '18' : '#f5f5f5' }"
        @click="activeAlgo = a.key"
      >
        <span class="algo-dot" :style="{ background: a.color }"></span>
        {{ a.label }} ({{ a.bi_count }}笔)
      </span>
    </div>

    <!-- K线 + 缠论标注 -->
    <div ref="chartRef" class="chart-container" v-if="result.status === 'ok'"></div>

    <van-empty v-else-if="result.status === 'error'" :description="result.message" />
    <van-empty v-else-if="searched && !loading" description="输入股票代码开始分析" />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { showToast } from 'vant'

const props = defineProps({ symbol: { type: String, default: '' } })
const symbol = ref(props.symbol || '')
const freq = ref('d')
const loading = ref(false)
const searched = ref(false)
const result = ref({ status: '' })
const chartRef = ref(null)
const activeAlgo = ref('宽松')

let mainChart = null
let allExtraSeries = []

const freqs = [
  { label: '日线', value: 'd' }, { label: '周线', value: 'w' },
  { label: '月线', value: 'm' },
  { label: '60分', value: '60m' }, { label: '30分', value: '30m' },
  { label: '15分', value: '15m' }, { label: '5分', value: '5m' },
  { label: '1分', value: '1m' },
]

const ALGO_COLORS = {
  '严格': '#ee0a24',
  '宽松': '#07c160',
  '极严': '#3b82f6',
  'ChanlunX': '#f59e0b',
}

const ALGO_META = {
  '严格': { color: '#ee0a24', width: 3, dash: [] },
  '宽松': { color: '#07c160', width: 3, dash: [] },
  '极严': { color: '#3b82f6', width: 3, dash: [] },
  'ChanlunX': { color: '#f59e0b', width: 3, dash: [] },
}

const ALGO_COLORS_BY_INDEX = ['#ee0a24', '#07c160', '#3b82f6', '#f59e0b']

const algorithms = computed(() => {
  return (result.value.algorithms || []).map((a, idx) => {
    const clr = ALGO_COLORS_BY_INDEX[idx] || '#999'
    return { key: a.label, label: a.label, color: clr, bi_count: a.bi_count }
  })
})

function norm(t) { return t ? t.replace(/\//g, '-').slice(0, 10) : null }

function destroyChart() {
  if (mainChart) { mainChart.remove(); mainChart = null }
  allExtraSeries.forEach(s => { try{s.remove()}catch(e){} })
  allExtraSeries = []
}

function renderChart() {
  if (!chartRef.value) return
  destroyChart()

  const klines = (result.value.klines || [])
  const rawAlgos = (result.value.algorithms || [])
  if (!klines.length || !rawAlgos.length) return

  const timeIdxMap = {}
  klines.forEach((k, i) => { timeIdxMap[k.time] = i })

  function findTime(t) {
    if (!t) return null
    const d = norm(t)
    if (d && timeIdxMap[d] !== undefined) return d
    // 分钟级数据用 Unix 时间戳匹配
    if (typeof t === 'string') return t
    return null
  }

  function findClosestTime(t, dir) {
    if (!t || !timeIdxMap) return null
    const ds = Object.keys(timeIdxMap)
    if (dir === 'next') {
      for (const d of ds) if (d >= t) return d
    } else {
      for (let i = ds.length-1; i >= 0; i--) if (ds[i] <= t) return ds[i]
    }
    return null
  }

  import('lightweight-charts').then(LW => {
    const lw = LW.default || LW
    const { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } = lw

    const container = chartRef.value
    if (!container) return

    mainChart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: '#FFFEF5' }, textColor: '#333' },
      grid: { vertLines: { color: '#f5f0e0' }, horzLines: { color: '#f5f0e0' } },
      rightPriceScale: { borderColor: '#e8e0c8' },
      timeScale: { borderColor: '#e8e0c8', timeVisible: freq.value.endsWith('m'), secondsVisible: false },
      crosshair: { mode: 0 },
      width: container.clientWidth,
      height: 420,
    })

    // K线
    const candleSerie = mainChart.addSeries(CandlestickSeries, {
      upColor: 'rgba(238,10,36,0.5)', downColor: 'rgba(7,193,96,0.5)',
      borderUpColor: 'rgba(238,10,36,0.6)', borderDownColor: 'rgba(7,193,96,0.6)',
      wickUpColor: 'rgba(238,10,36,0.6)', wickDownColor: 'rgba(7,193,96,0.6)',
    })
    candleSerie.setData(klines.map(k => ({
      time: k.time, open: k.open, high: k.high, low: k.low, close: k.close,
    })))

    // 成交量
    const volSerie = mainChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'volume',
    })
    mainChart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    volSerie.setData(klines.map(k => ({
      time: k.time, value: k.volume || 0,
      color: k.close >= k.open ? 'rgba(238,10,36,0.1)' : 'rgba(7,193,96,0.1)',
    })))

    // 找到当前选中的算法（从原始数据中获取bis）
    const algoLabel = activeAlgo.value
    const algoData = rawAlgos.find(a => a.label === algoLabel)
    const algoIdx = rawAlgos.findIndex(a => a.label === algoLabel)
    if (!algoData) return
    const clr = ALGO_COLORS_BY_INDEX[algoIdx] || '#666'
    const bis = algoData.bis || []
    const lineW = 3
    const isMinute = freq.value.endsWith('m') && freq.value !== 'm'

    // 统一时间格式：CL 库返回 YYYY/MM/DD，K线是 YYYY-MM-DD
    function normT(t) {
      if (!t) return null
      if (typeof t === 'string') {
        return t.replace(/\//g, '-').slice(0, 10)
      }
      return t
    }

    // ── 画笔 (BI) ──
    for (let i = 0; i < bis.length; i++) {
      const bi = bis[i]
      let st = normT(bi.start_time)
      let et = normT(bi.end_time)

      if (!st && i > 0 && bis[i-1].end_time) {
        const prevT = normT(bis[i-1].end_time)
        const prevIdx = klines.findIndex(k => k.time === prevT)
        if (prevIdx >= 0 && prevIdx + 1 < klines.length)
          st = klines[prevIdx + 1].time
      }
      if (!et && st && klines.length > 0) {
        const si = klines.findIndex(k => k.time === st)
        et = si >= 0 && si + 2 < klines.length ? klines[si + 2].time : klines[klines.length-1].time
      }
      if (!st || !et || st === et) continue

      const s = mainChart.addSeries(LineSeries, {
        color: clr, lineWidth: lineW, lineStyle: 0,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      s.setData([
        { time: st, value: bi.type === 'up' ? bi.low : bi.high },
        { time: et, value: bi.type === 'up' ? bi.high : bi.low },
      ])
      allExtraSeries.push(s)
    }

    // 端点标记
    const markers = []
    for (let i = 0; i < bis.length; i++) {
      const bi = bis[i]
      let t = normT(bi.end_time)
      if (!t) t = klines[Math.min(Math.floor((i+1)/bis.length*klines.length), klines.length-1)].time
      markers.push({
        time: t, position: 'inBar', color: clr, shape: 'circle', size: 1,
      })
    }
    if (markers.length) {
      const ms = mainChart.addSeries(LineSeries, {
        color: 'transparent', lastValueVisible: false, priceLineVisible: false,
      })
      ms.setData([{ time: klines[0].time, value: bis[0]?.low || klines[0].low }])
      ms.setMarkers(markers)
      allExtraSeries.push(ms)
    }

    // ── 画线段 (XD) ──
    const xds = algoData.xds || []
    for (let i = 0; i < xds.length; i++) {
      const xd = xds[i]
      let st = normT(xd.start_time), et = normT(xd.end_time)
      if (!st || !et || st === et) continue
      const s = mainChart.addSeries(LineSeries, {
        color: clr, lineWidth: 2, lineStyle: 1,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      s.setData([
        { time: st, value: xd.type === 'up' ? xd.low : xd.high },
        { time: et, value: xd.type === 'up' ? xd.high : xd.low },
      ])
      allExtraSeries.push(s)
    }
    // 线段端点
    for (let i = 0; i < xds.length; i++) {
      const xd = xds[i]
      let t = normT(xd.end_time)
      if (!t) continue
      markers.push({
        time: t, position: 'inBar', color: clr, shape: 'diamond', size: 1,
      })
    }

    // ── 画中枢 (ZS) 矩形 ──
    const zss = algoData.zss || []
    const zsColors = ['#e74c3c', '#2ecc71', '#3498db', '#f39c12', '#9b59b6', '#1abc9c']
    for (let zi = 0; zi < zss.length; zi++) {
      const zs = zss[zi]
      if (!zs.zg || !zs.zd) continue
      const zsStart = normT(zs.start_time) || klines[0].time
      const zsEnd = normT(zs.end_time) || klines[klines.length-1].time
      
      const zsClr = zsColors[zi % zsColors.length]
      
      // ZG 上轨
      const zgS = mainChart.addSeries(LineSeries, {
        color: zsClr, lineWidth: 1, lineStyle: 3,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      zgS.setData([{ time: zsStart, value: zs.zg }, { time: zsEnd, value: zs.zg }])
      allExtraSeries.push(zgS)
      
      // ZD 下轨
      const zdS = mainChart.addSeries(LineSeries, {
        color: zsClr, lineWidth: 1, lineStyle: 3,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      zdS.setData([{ time: zsStart, value: zs.zd }, { time: zsEnd, value: zs.zd }])
      allExtraSeries.push(zdS)
      
      // 左侧竖线连接 zg-zd
      const leftS = mainChart.addSeries(LineSeries, {
        color: zsClr, lineWidth: 1, lineStyle: 3,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      leftS.setData([{ time: zsStart, value: zs.zg }, { time: zsStart, value: zs.zd }])
      allExtraSeries.push(leftS)
      
      // 右侧竖线连接 zg-zd
      const rightS = mainChart.addSeries(LineSeries, {
        color: zsClr, lineWidth: 1, lineStyle: 3,
        lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
      })
      rightS.setData([{ time: zsEnd, value: zs.zg }, { time: zsEnd, value: zs.zd }])
      allExtraSeries.push(rightS)

      // GG 最高点标记
      if (zs.gg && zs.gg !== zs.zg) {
        markers.push({ time: zsEnd, position: 'aboveBar', color: zsClr, shape: 'arrowDown', text: 'G' })
      }
      if (zs.dd && zs.dd !== zs.zd) {
        markers.push({ time: zsEnd, position: 'belowBar', color: zsClr, shape: 'arrowUp', text: 'D' })
      }
    }

    mainChart.timeScale().fitContent()
  })
}

// 切换算法时重绘
watch(activeAlgo, () => { nextTick(renderChart) })

function doAnalyze() {
  const sym = symbol.value.trim()
  if (!sym) { showToast({ message: '请输入股票代码', type: 'fail' }); return }
  loading.value = true; searched.value = true
  result.value = { status: '' }
  activeAlgo.value = '宽松'

  fetch(`/api/v1/chanlun/compare/${sym}?days=365&freq=${freq.value}`)
    .then(r => r.json())
    .then(data => {
      result.value = data
      if (data.status === 'ok') {
        const info = (data.algorithms || []).map(a => `${a.label}:${a.bi_count}笔`).join(' ')
        showToast(`✅ ${info}`)
        nextTick(renderChart)
      } else {
        showToast({ message: data.message || '分析失败', type: 'fail' })
      }
    })
    .catch(e => showToast({ message: '请求失败', type: 'fail' }))
    .finally(() => { loading.value = false })
}

function switchFreq(f) { freq.value = f; doAnalyze() }
// 如果通过路由传入 symbol，自动分析
onMounted(() => {
  if (props.symbol) {
    doAnalyze()
  }
})

onBeforeUnmount(() => { destroyChart() })
</script>

<style scoped>
.search-area { background: #fff; }
.search-row { display: flex; align-items: center; }
.freq-switch { display: flex; gap: 2px; padding: 0 8px; flex-shrink: 0; }
.freq-btn { font-size: 11px; padding: 4px 8px; border-radius: 4px; color: #666; background: #f5f5f5; white-space: nowrap; }
.freq-btn.active { color: #fff; background: #1989fa; font-weight: 600; }
.chart-container { width: 100%; height: 420px; background: #FFFEF5; }

.algo-bar {
  display: flex; gap: 6px; padding: 6px 12px;
  background: #fff; border-bottom: 1px solid #eee;
}
.algo-btn {
  font-size: 12px; padding: 4px 10px; border-radius: 12px;
  border: 1px solid #ddd; cursor: pointer; display: flex;
  align-items: center; gap: 4px; color: #666;
}
.algo-btn.active {
  border-color: var(--accent, #1989fa);
  color: var(--accent, #1989fa);
  background: rgba(59, 130, 246, 0.08);
  font-weight: 600;
}
.algo-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
</style>
