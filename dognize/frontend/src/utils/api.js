import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

export function getKline(symbol, params = {}) {
  return api.get(`/kline/${symbol}`, { params })
}

export function getFundamentals(symbol) {
  return api.get(`/fundamentals/${symbol}`)
}

export function getHealth() {
  return api.get('/health')
}

export function screenStocks(params = {}) {
  return api.get('/screener', { params })
}

export function getStockList() {
  return api.get('/stocks', { timeout: 60000 })
}

export function getBigBuy(symbol, days = 60) {
  return api.get(`/bigbuy/${symbol}`, { params: { days } })
}

export function getBigDealSummary(symbol, limit = 60) {
  return api.get(`/big-deal-summary/${symbol}`, { params: { limit } })
}

export function getBigBuySummary(symbol, limit = 60) {
  return api.get(`/big-buy-summary/${symbol}`, { params: { limit } })
}

// === 缠论相关 ===
export function getChanlunCompare(symbol, params = {}) {
  return api.get(`/chanlun/compare/${symbol}`, { params })
}

export function getChanlunAnalysis(symbol, params = {}) {
  return api.get(`/chanlun/analysis/${symbol}`, { params })
}

// === 回测相关 ===
export function getBacktestStrategies() {
  return api.get('/backtest/strategies')
}

export function runBacktest(params = {}) {
  return api.post('/backtest/run', params)
}

export function getBacktestResults(params = {}) {
  return api.get('/backtest/results', { params })
}

// === 交易相关 ===
export function getTradeAccounts() {
  return api.get('/trade/accounts')
}

export function getTradePositions() {
  return api.get('/trade/positions')
}

export function getTradeOrders(params = {}) {
  return api.get('/trade/orders', { params })
}

export function placeOrder(params = {}) {
  return api.post('/trade/order', params)
}

export function getTradeStatus() {
  return api.get('/trade/status')
}
