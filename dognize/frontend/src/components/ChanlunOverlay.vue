<template>
  <div class="chanlun-overlay" v-if="visible">
    <div class="overlay-toolbar">
      <span class="overlay-title">📐 缠论标注</span>
      <van-switch v-model="showBis" size="20px" @change="$emit('update:showBis', showBis)" />
      <span style="font-size:12px;color:#666;margin:0 8px">笔</span>
      <van-switch v-model="showXds" size="20px" @change="$emit('update:showXds', showXds)" />
      <span style="font-size:12px;color:#666;margin:0 8px">段</span>
      <van-switch v-model="showZss" size="20px" @change="$emit('update:showZss', showZss)" />
      <span style="font-size:12px;color:#666;margin:0 4px">中枢</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  data: { type: Object, default: () => ({}) },
  modelValue: { type: Object, default: () => ({}) },
  showBis: { type: Boolean, default: true },
  showXds: { type: Boolean, default: true },
  showZss: { type: Boolean, default: true },
})

const emit = defineEmits(['update:showBis', 'update:showXds', 'update:showZss'])

const showBis = ref(props.showBis)
const showXds = ref(props.showXds)
const showZss = ref(props.showZss)
</script>

<style scoped>
.chanlun-overlay {
  padding: 6px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}
.overlay-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
}
.overlay-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-right: 8px;
}
</style>
