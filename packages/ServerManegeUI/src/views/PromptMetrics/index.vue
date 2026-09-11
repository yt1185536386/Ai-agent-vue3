<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">Prompt 监控</h2>
        <div class="page-subtitle">模板调用量、版本分布、Token 消耗与回归通过率</div>
      </div>
      <div class="head-actions">
        <el-select v-model="days" size="small" style="width: 120px" @change="load">
          <el-option label="近 7 天" :value="7" />
          <el-option label="近 14 天" :value="14" />
          <el-option label="近 30 天" :value="30" />
        </el-select>
        <el-button :icon="Refresh" circle @click="load" />
      </div>
    </div>

    <!-- 顶部 stat 卡 -->
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

    <!-- 图表区:版本分布 + token 趋势(随模板选择联动) -->
    <div class="page-card chart-card">
      <div class="chart-head">
        <div class="chart-title">
          模板趋势
          <el-select v-model="trendKey" size="small" style="width: 220px; margin-left: 12px" @change="loadTrend">
            <el-option v-for="t in overview?.templates ?? []" :key="t.template_key"
              :label="t.template_key" :value="t.template_key" />
          </el-select>
        </div>
        <el-radio-group v-model="chartTab" size="small">
          <el-radio-button value="dist">版本分布(按天)</el-radio-button>
          <el-radio-button value="token">Prompt Token(按版本)</el-radio-button>
        </el-radio-group>
      </div>
      <div ref="chartRef" class="chart" v-loading="trendLoading" />
    </div>

    <!-- 模板明细表 -->
    <div class="page-card table-card">
      <div class="chart-title">模板明细<span class="chart-sub">点击行钻取上方趋势</span></div>
      <el-table :data="overview?.templates ?? []" size="small" @row-click="(r: PeTemplateStat) => { trendKey = r.template_key; loadTrend() }">
        <el-table-column prop="template_key" label="模板 key" min-width="160" />
        <el-table-column label="版本分布" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="v in row.versions" :key="v.version" size="small" effect="plain" style="margin-right: 4px">
              v{{ v.version }} × {{ v.call_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="call_count" label="调用量" width="90" sortable />
        <el-table-column label="平均 prompt token" width="140">
          <template #default="{ row }">{{ row.avg_prompt_tokens ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="平均耗时" width="100">
          <template #default="{ row }">{{ row.avg_latency_ms }} ms</template>
        </el-table-column>
        <el-table-column label="回归通过率" width="110">
          <template #default="{ row }">
            <span v-if="row.eval_pass_rate == null" class="muted">未评测</span>
            <el-tag v-else :type="row.eval_pass_rate >= 0.9 ? 'success' : row.eval_pass_rate >= 0.7 ? 'warning' : 'danger'" size="small">
              {{ (row.eval_pass_rate * 100).toFixed(0) }}%
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="overview?.silent_templates?.length" class="silent-tip">
        沉默模板(近 7 天零调用):{{ overview.silent_templates.join('、') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import echarts, { type ECharts, type EChartsOption } from '@/utils/echarts'
import { Refresh, TrendCharts, Lightning, Document, CircleCheck } from '@element-plus/icons-vue'
import { promptApi, type PeOverview, type PeTemplateStat, type PeTrendPoint } from '@/api'

const PALETTE = ['#22d3ee', '#8b5cf6', '#34d399', '#fbbf24', '#f43f5e', '#3b82f6', '#ec4899', '#14b8a6']

const days = ref(30)
const overview = ref<PeOverview>()
const todayCalls = ref(0)
const trendKey = ref('agent.system')
const trendPoints = ref<PeTrendPoint[]>([])
const trendLoading = ref(false)
const chartTab = ref<'dist' | 'token'>('dist')

const chartRef = ref<HTMLDivElement>()
let chart: ECharts | null = null

const cards = computed(() => {
  const ov = overview.value
  const tokens = ov?.templates.filter((t) => t.avg_prompt_tokens != null) ?? []
  const avgTokens = tokens.length
    ? Math.round(tokens.reduce((s, t) => s + (t.avg_prompt_tokens ?? 0) * t.call_count, 0)
      / Math.max(1, tokens.reduce((s, t) => s + t.call_count, 0)))
    : 0
  const rates = (ov?.templates ?? []).map((t) => t.eval_pass_rate).filter((r): r is number => r != null)
  const latestRate = rates.length ? Math.max(...rates) : null
  return [
    { label: '今日调用', value: String(todayCalls.value), unit: '次', icon: TrendCharts, color: '#2563eb' },
    { label: '活跃模板数', value: String(ov?.active_templates ?? 0), unit: '个', icon: Document, color: '#8b5cf6' },
    { label: '平均 prompt token', value: String(avgTokens), unit: 'tokens', icon: Lightning, color: '#10b981' },
    {
      label: '最近回归通过率',
      value: latestRate == null ? '—' : (latestRate * 100).toFixed(0) + '%',
      unit: latestRate == null ? '未评测' : '', icon: CircleCheck, color: '#f59e0b',
    },
  ]
})

async function load() {
  const [{ data: ov }, { data: today }] = await Promise.all([
    promptApi.overview(days.value),
    promptApi.overview(1),
  ])
  overview.value = ov
  todayCalls.value = today.total_calls
  if (!ov.templates.some((t) => t.template_key === trendKey.value) && ov.templates.length) {
    trendKey.value = ov.templates[0].template_key
  }
  await loadTrend()
}

async function loadTrend() {
  trendLoading.value = true
  try {
    const { data } = await promptApi.templateTrend(trendKey.value, days.value)
    trendPoints.value = data.points
    renderChart()
  } finally {
    trendLoading.value = false
  }
}

function renderChart() {
  if (!chart) return
  const points = trendPoints.value
  const dates = [...new Set(points.map((p) => p.date))].sort()
  const versions = [...new Set(points.map((p) => p.version))].sort((a, b) => a - b)
  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, type: 'scroll', itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 20, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: dates.map((d) => d.slice(5)), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' },
    series: versions.map((v, i) => {
      const rows = dates.map((d) => points.find((p) => p.date === d && p.version === v))
      if (chartTab.value === 'dist') {
        return {
          name: `v${v}`, type: 'bar' as const, stack: 'total', barWidth: 24,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
          data: rows.map((r) => r?.call_count ?? 0),
        }
      }
      return {
        name: `v${v}`, type: 'line' as const, smooth: true, connectNulls: true,
        itemStyle: { color: PALETTE[i % PALETTE.length] },
        data: rows.map((r) => r?.avg_prompt_tokens ?? null),
      }
    }),
  }
  chart.setOption(option, true)
}

watch(chartTab, renderChart)

onMounted(() => {
  chart = echarts.init(chartRef.value!)
  window.addEventListener('resize', () => chart?.resize())
  load()
})
onUnmounted(() => chart?.dispose())
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 14px 16px; }
.stat-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #606266; }
.stat-value { margin-top: 8px; }
.stat-value .num { font-size: 26px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.stat-value .unit { font-size: 12px; color: #909399; margin-left: 4px; }
.chart-card { padding: 14px 18px; margin-bottom: 14px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; }
.chart-title { font-size: 16px; font-weight: 600; color: #1f2d3d; display: flex; align-items: center; }
.chart-sub { font-size: 12px; font-weight: 400; color: #909399; margin-left: 8px; }
.chart { height: 340px; margin-top: 12px; }
.table-card { padding: 14px 18px; }
.table-card .el-table { margin-top: 10px; }
.table-card :deep(.el-table__row) { cursor: pointer; }
.muted { color: #c0c4cc; font-size: 12px; }
.silent-tip { margin-top: 10px; font-size: 12px; color: #e6a23c; }
@media (max-width: 1200px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
</style>
