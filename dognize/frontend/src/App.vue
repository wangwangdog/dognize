<template>
  <van-config-provider :theme="theme">
    <router-view />
    <van-tabbar v-model="active" route active-color="#1989fa" :border="true" safe-area-inset-bottom>
      <van-tabbar-item icon="search" to="/">搜索</van-tabbar-item>
      <van-tabbar-item icon="gem-o" to="/strategies">策略</van-tabbar-item>
      <van-tabbar-item icon="chart-trending-o" to="/chanlun">缠论</van-tabbar-item>
      <van-tabbar-item icon="clock-o" to="/backtest">回测</van-tabbar-item>
      <van-tabbar-item icon="exchange" to="/trade">交易</van-tabbar-item>
      <van-tabbar-item icon="contact" to="/settings">我的</van-tabbar-item>
    </van-tabbar>
  </van-config-provider>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const theme = ref('light')
const route = useRoute()

const tabRoutes = ['/', '/strategies', '/chanlun', '/backtest', '/trade', '/settings']
const tabMap = {}
tabRoutes.forEach((p, i) => { tabMap[p] = i })

const active = ref(tabMap[route.path] !== undefined ? tabMap[route.path] : 0)
</script>

<style>
:root {
  --van-nav-bar-height: 44px;
  --van-tabbar-height: 50px;
}
</style>
