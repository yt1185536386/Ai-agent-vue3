<template>
  <div>
    <!-- 顶部:标题 + 时间范围 + 用户筛选 + 操作 -->
    <div class="head-row">
      <div>
        <h2 class="page-title">数据看板</h2>
        <div class="page-subtitle">实时监控调用、Token 消耗与错误率</div>
      </div>
      <div class="head-actions">
        <el-date-picker
          v-model="range"
          type="datetimerange"
          range-separator="→"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          format="YYYY-MM-DD HH:mm:ss"
          style="width: 340px"
          @change="load"
        />
        <el-select v-model="username" placeholder="搜索用户" clearable filterable style="width: 160px" @change="load">
          <el-option v-for="u in userOptions" :key="u" :label="u" :value="u" />
        </el-select>
        <el-button :icon="Refresh" circle @click="load" />
        <el-button :icon="Download" @click="exportCsv">导出</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <div v-for="card in cards" :key="card.label" class="stat-card">
        <div class="stat-label">
          <el-icon :color="card.color"><component :is="card.icon" /></el-icon>
          <span>{{ card.label }}</span>
        </div>
        <div class="stat-value">
          <span class="num">{{ card.value }}</span>
          <span class="unit">{{ card.unit }}</span>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="page-card chart-card">
      <div class="chart-head">
        <el-radio-group v-model="tab" size="small">
          <el-radio-button value="channel">渠道调用</el-radio-button>
          <el-radio-button value="model">模型调用</el-radio-button>
          <el-radio-button value="user">用户</el-radio-button>
          <el-radio-button value="trend">调用趋势</el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="metric" size="small">
          <el-radio-button value="calls">调用</el-radio-button>
          <el-radio-button value="tokens">Token</el-radio-button>
        </el-radio-group>
      </div>

      <div class="chart-title-row">
        <div class="chart-title">
          {{ chartTitle }} <span class="chart-sub">{{ chartSub }}</span>
        </div>
        <div v-if="tab === 'user'" class="chart-meta">共 {{ modelCount }} 个模型</div>
      </div>

      <div ref="chartRef" class="chart" v-loading="loading" />
    </div>

    <div class="foot-row">
      <div class="auto-refresh">
        自动刷新:
        <el-select v-model="autoRefresh" size="small" style="width: 90px">
          <el-option label="关闭" :value="0" />
          <el-option label="10 秒" :value="10" />
          <el-option label="30 秒" :value="30" />
          <el-option label="60 秒" :value="60" />
        </el-select>
      </div>
      <div class="last-sync">最后同步: {{ lastSync }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import echarts, { type ECharts, type EChartsOption } from '@/utils/echarts'
import dayjs from 'dayjs'
import { Refresh, Download, TrendCharts, Lightning, Timer, Warning, Coin } from '@element-plus/icons-vue'
import { statsApi, type Overview } from '@/api'

const PALETTE = ['#22d3ee', '#8b5cf6', '#34d399', '#fbbf24', '#f43f5e', '#3b82f6', '#ec4899', '#14b8a6', '#a78bfa', '#fb923c', '#06b6d4', '#84cc16']

const range = ref<[Date, Date]>([
  dayjs().startOf('day').toDate(),
  dayjs().endOf('day').toDate(),
])
const username = ref<string>()
const tab = ref<'channel' | 'model' | 'user' | 'trend'>('user')
const metric = ref<'calls' | 'tokens'>('calls')
const loading = ref(false)
const overview = ref<Overview>()
const userOptions = ref<string[]>([])
const lastSync = ref('-')
const autoRefresh = ref(0)
let refreshTimer = 0

const chartRef = ref<HTMLDivElement>()
let chart: ECharts | null = null

const cards = computed(() => {
  const s = overview.value?.summary
  return [
    { label: '当前区间调用', value: fmt(s?.totalCalls ?? 0), unit: '次', icon: TrendCharts, color: '#2563eb' },
    { label: '当前区间令牌数', value: fmt(s?.totalTokens ?? 0), unit: '个令牌', icon: Lightning, color: '#8b5cf6' },
    { label: '每分钟请求', value: fmt(s?.callsPerMinute ?? 0), unit: '次/分钟', icon: Timer, color: '#10b981' },
    { label: '每分钟令牌数', value: fmt(s?.tokensPerMinute ?? 0), unit: '个/分钟', icon: Coin, color: '#f59e0b' },
    { label: '当前区间错误率', value: (s?.errorRate ?? 0).toFixed(2) + '%', unit: '', icon: Warning, color: '#ef4444' },
  ]
})

const chartTitle = computed(() => ({ channel: '渠道调用', model: '模型调用', user: '用户调用', trend: '调用趋势' }[tab.value]))
const chartSub = computed(() => ({
  channel: '各渠道调用量分布', model: '各模型调用量分布',
  user: '各用户调用量分布', trend: '按小时统计',
}[tab.value]))
const modelCount = computed(() => new Set((overview.value?.userModel || []).map((r) => r.model)).size)

function fmt(n: number): string {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k'
  return n % 1 === 0 ? String(n) : n.toFixed(1)
}

async function load() {
  if (!range.value?.[0]) return
  loading.value = true
  try {
    const { data } = await statsApi.overview({
      start: dayjs(range.value[0]).format('YYYY-MM-DDTHH:mm:ss'),
      end: dayjs(range.value[1]).format('YYYY-MM-DDTHH:mm:ss'),
      username: username.value || undefined,
    })
    overview.value = data.data
    userOptions.value = data.data.byUser.map((r) => r.groupKey)
    lastSync.value = dayjs().format('YY-MM-DD HH:mm')
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  const d = overview.value
  if (!d || !chart) return
  const key = metric.value
  let option: EChartsOption

  if (tab.value === 'user') {
    const users = [...new Set(d.userModel.map((r) => r.username))]
    const models = [...new Set(d.userModel.map((r) => r.model))]
    const totals = users.map((u) =>
      d.userModel.filter((r) => r.username === u).reduce((s, r) => s + r[key], 0))
    // 按总量降序
    const order = users.map((u, i) => i).sort((a, b) => totals[b] - totals[a])
    const sortedUsers = order.map((i) => users[i])
    const sortedTotals = order.map((i) => totals[i])
    option = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmt(Number(v)) },
      legend: { bottom: 0, type: 'scroll', itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 30, bottom: 90 },
      xAxis: { type: 'category', data: sortedUsers, axisLabel: { rotate: 30, fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
      series: [
        ...models.map((m, i) => ({
          name: m,
          type: 'bar' as const,
          stack: 'total',
          barWidth: 26,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
          data: sortedUsers.map((u) => {
            const row = d.userModel.find((r) => r.username === u && r.model === m)
            return row ? row[key] : 0
          }),
        })),
        {
          name: '合计', type: 'bar' as const, barGap: '-100%', barWidth: 26,
          itemStyle: { color: 'transparent' }, tooltip: { show: false },
          data: sortedTotals, label: { show: true, position: 'top', formatter: (p: { value?: unknown }) => fmt(Number(p.value)), fontSize: 11 },
          z: 1, silent: true, legendHoverLink: false,
        },
      ],
    }
  } else if (tab.value === 'trend') {
    option = {
      tooltip: { trigger: 'axis', valueFormatter: (v) => fmt(Number(v)) },
      grid: { left: 60, right: 20, top: 30, bottom: 50 },
      xAxis: { type: 'category', data: d.trend.map((r) => r.groupKey.slice(5)), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
      series: [{
        name: key === 'calls' ? '调用量' : 'Token',
        type: 'line', smooth: true, areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#2563eb' },
        data: d.trend.map((r) => r[key]),
      }],
    }
  } else {
    const rows = tab.value === 'model' ? d.byModel : d.byChannel
    option = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmt(Number(v)) },
      grid: { left: 60, right: 20, top: 30, bottom: 60 },
      xAxis: { type: 'category', data: rows.map((r) => r.groupKey), axisLabel: { rotate: 25, fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
      series: [{
        name: key === 'calls' ? '调用量' : 'Token',
        type: 'bar', barWidth: 30,
        itemStyle: { color: tab.value === 'model' ? '#8b5cf6' : '#22d3ee', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', formatter: (p: { value?: unknown }) => fmt(Number(p.value)), fontSize: 11 },
        data: rows.map((r) => r[key]),
      }],
    }
  }
  chart.setOption(option, true)
}

function exportCsv() {
  const d = overview.value
  if (!d) return
  const lines = ['username,model,calls,tokens',
    ...d.userModel.map((r) => `${r.username},${r.model},${r.calls},${r.tokens}`)]
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `gateway-stats-${dayjs().format('YYYYMMDD-HHmm')}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

watch([tab, metric], renderChart)
watch(autoRefresh, (sec) => {
  clearInterval(refreshTimer)
  if (sec > 0) refreshTimer = window.setInterval(load, sec * 1000)
})

onMounted(() => {
  chart = echarts.init(chartRef.value!)
  window.addEventListener('resize', () => chart?.resize())
  load()
})
onUnmounted(() => {
  clearInterval(refreshTimer)
  chart?.dispose()
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 14px 16px; }
.stat-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #606266; }
.stat-value { margin-top: 8px; }
.stat-value .num { font-size: 26px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.stat-value .unit { font-size: 12px; color: #909399; margin-left: 4px; }
.chart-card { padding: 14px 18px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; }
.chart-title-row { display: flex; justify-content: space-between; align-items: baseline; margin: 16px 0 4px; }
.chart-title { font-size: 16px; font-weight: 600; color: #1f2d3d; }
.chart-sub { font-size: 12px; font-weight: 400; color: #909399; margin-left: 8px; }
.chart-meta { font-size: 12px; color: #909399; }
.chart { height: 380px; }
.foot-row { display: flex; justify-content: space-between; margin-top: 10px; font-size: 12px; color: #909399; }
.auto-refresh { display: flex; align-items: center; gap: 6px; }
@media (max-width: 1200px) { .stat-row { grid-template-columns: repeat(3, 1fr); } }
</style>
