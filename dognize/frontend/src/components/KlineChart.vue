<template>
  <div class="kline-chart-wrap">
    <div class="chart-container" ref="chartRef">
      <div class="chart-watermark">{{ watermark }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  indicators: { type: Object, default: () => ({}) },
  period: { type: String, default: 'daily' },
  watermark: { type: String, default: '' },
})

const chartRef = ref(null)
let chart = null
let candleSeries = null
let volSeries = null
let extraSeries = []

function destroyChart() {
  if (chart) { chart.remove(); chart = null }
  extraSeries.forEach(s => { try { s.remove() } catch(e) {} })
  extraSeries = []
  candleSeries = null
  volSeries = null
}

function makeTime(d, period) {
  const isIntraday = ['15min', '30min', '60min'].includes(period)
  if (isIntraday) {
    const dt = new Date(d.date.replace(' ', 'T') + '+08:00')
    return Math.floor(dt.getTime() / 1000)
  }
  return d.date.slice(0, 10)
}

function renderChart() {
  if (!chartRef.value || !props.data.length) return
  destroyChart()

  import('lightweight-charts').then(LW => {
    const lw = LW.default || LW
    const { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } = lw

    chart = createChart(chartRef.value, {
      layout: {
        background: { type: ColorType.Solid, color: '#FFFEF5' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f5f0e0' },
        horzLines: { color: '#f5f0e0' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#e8e0c8' },
      timeScale: {
        borderColor: '#e8e0c8',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true },
      handleScale: { axisPressedMouse: true, mouseWheel: true, pinch: true },
      width: chartRef.value.clientWidth,
      height: 360,
    })

    const times = props.data.map(d => makeTime(d, props.period))

    // K线
    candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ee0a24',
      downColor: '#07c160',
      borderUpColor: '#ee0a24',
      borderDownColor: '#07c160',
      wickUpColor: '#ee0a24',
      wickDownColor: '#07c160',
    })
    candleSeries.setData(props.data.map((d, i) => ({
      time: times[i],
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    })))

    // 成交量
    volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    volSeries.setData(props.data.map((d, i) => ({
      time: times[i],
      value: d.volume || 0,
      color: d.close >= d.open ? 'rgba(238,10,36,0.3)' : 'rgba(7,193,96,0.3)',
    })))

    // 均线
    if (props.indicators?.ma) {
      const periods = [5, 10, 20, 60]
      const colors = ['#f7931a', '#1890ff', '#52c41a', '#722ed1']
      periods.forEach((p, idx) => {
        const key = `MA${p}`
        if (props.indicators.ma[key]?.length) {
          const line = chart.addSeries(LineSeries, {
            color: colors[idx],
            lineWidth: 1,
            lastValueVisible: false,
            priceLineVisible: false,
          })
          line.setData(props.data.map((d, i) => ({
            time: times[i],
            value: props.indicators.ma[key][i],
          })).filter(d => d.value !== null && !isNaN(d.value)))
          extraSeries.push(line)
        }
      })
    }

    chart.timeScale().fitContent()
  })
}

watch(() => props.data, () => { nextTick(renderChart) }, { deep: true })

onMounted(() => { nextTick(renderChart) })
onBeforeUnmount(() => { destroyChart() })

defineExpose({ renderChart, destroyChart })
</script>

<style scoped>
.kline-chart-wrap {
  width: 100%;
}
.chart-container {
  position: relative;
  width: 100%;
  height: 360px;
}
.chart-watermark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 48px;
  font-weight: bold;
  color: rgba(0, 0, 0, 0.05);
  pointer-events: none;
  z-index: 1;
  white-space: nowrap;
}
</style>
