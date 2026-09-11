<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">Context 监控</h2>
        <div class="page-subtitle">检索召回质量与 Context 水位(线上发现漂移,离线指标定精度)</div>
      </div>
      <div class="head-actions">
        <el-select v-model="days" size="small" style="width: 120px" @change="load">
          <el-option label="近 7 天" :value="7" />
          <el-option label="近 14 天" :value="14" />
          <el-option label="近 30 天" :value="30" />
        </el-select>
        <el-button size="small" @click="strategyDialog = true">检索策略</el-button>
        <el-button size="small" type="primary" plain :loading="evalRunning" @click="onRunEval">跑离线评测</el-button>
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

    <!-- 图表区 -->
    <div class="charts-grid">
      <div class="page-card chart-card">
        <div class="chart-title">最高相似度分布<span class="chart-sub">判断阈值合理性 / embedding 区分度</span></div>
        <div ref="histRef" class="chart" />
      </div>
      <div class="page-card chart-card">
        <div class="chart-title">Context Token 趋势<span class="chart-sub">均值 + p95</span></div>
        <div ref="tokenRef" class="chart" />
      </div>
      <div class="page-card chart-card">
        <div class="chart-title">Context 组成占比<span class="chart-sub">system / history / tool(估算)</span></div>
        <div ref="composeRef" class="chart" />
      </div>
      <div class="page-card chart-card">
        <div class="chart-title">离线评测趋势<span class="chart-sub">Recall@K / Precision@K(跑 eval 后上板)</span></div>
        <div ref="evalRef" class="chart" />
      </div>
    </div>

    <!-- 底部榜单 -->
    <div class="lists-grid">
      <div class="page-card list-card">
        <div class="chart-title">零结果 query 榜<span class="chart-sub">回收为评测用例可补 ground truth</span></div>
        <el-table :data="overview?.zero_result_top ?? []" size="small">
          <el-table-column prop="query" label="query" min-width="200" show-overflow-tooltip />
          <el-table-column prop="count" label="次数" width="70" />
          <el-table-column label="候选最高分" width="100">
            <template #default="{ row }">{{ row.avg_max_score.toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button size="small" type="warning" plain @click="onRecycleQuery(row.query)">回收为用例</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="page-card list-card">
        <div class="chart-title">低分检索事件榜<span class="chart-sub">按 max_score 升序</span></div>
        <el-table :data="overview?.low_score_events ?? []" size="small">
          <el-table-column prop="query" label="query" min-width="200" show-overflow-tooltip />
          <el-table-column label="最高分" width="80">
            <template #default="{ row }">{{ row.max_score.toFixed(3) }}</template>
          </el-table-column>
          <el-table-column prop="hit_count" label="命中" width="70" />
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button size="small" type="warning" plain @click="onRecycleEvent(row.id)">回收为用例</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 检索策略对话框 -->
    <el-dialog v-model="strategyDialog" title="检索策略(调参实验)" width="480px">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 12px"
        title="改 size/overlap 需重建索引(重切+重 embedding)才对存量文档生效;top_k/threshold 即时生效" />
      <el-form label-width="110px" size="default">
        <el-form-item label="策略标识">
          <el-input v-model="strategyForm.strategy" placeholder="留空按参数自动生成" />
        </el-form-item>
        <el-form-item label="切分 size">
          <el-input-number v-model="strategyForm.size" :min="100" :max="4000" />
        </el-form-item>
        <el-form-item label="重叠 overlap">
          <el-input-number v-model="strategyForm.overlap" :min="0" :max="1000" />
        </el-form-item>
        <el-form-item label="top_k">
          <el-input-number v-model="strategyForm.top_k" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="相似度阈值">
          <el-input-number v-model="strategyForm.threshold" :min="0" :max="1" :step="0.05" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="strategyDialog = false">取消</el-button>
        <el-button type="primary" @click="onSaveStrategy">保存生效</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import echarts, { type ECharts } from '@/utils/echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, Aim, CircleClose, TrendCharts, Coin,
} from '@element-plus/icons-vue'
import { contextApi, type CxOverview, type CxTrendPoint } from '@/api'

const days = ref(14)
const overview = ref<CxOverview>()
const series = ref<CxTrendPoint[]>([])
const evalRunning = ref(false)
const strategyDialog = ref(false)
const strategyForm = reactive({ strategy: '', size: 600, overlap: 80, top_k: 3, threshold: 0.3 })

const histRef = ref<HTMLDivElement>()
const tokenRef = ref<HTMLDivElement>()
const composeRef = ref<HTMLDivElement>()
const evalRef = ref<HTMLDivElement>()
let histChart: ECharts | null = null
let tokenChart: ECharts | null = null
let composeChart: ECharts | null = null
let evalChart: ECharts | null = null

const cards = computed(() => {
  const ov = overview.value
  const hitRate = ov && ov.retrieval_count ? 1 - ov.zero_result_rate : 0
  return [
    { label: '检索命中率', value: (hitRate * 100).toFixed(1) + '%', unit: `${ov?.retrieval_count ?? 0} 次检索`, icon: Aim, color: '#2563eb' },
    { label: '零结果率', value: ((ov?.zero_result_rate ?? 0) * 100).toFixed(1) + '%', unit: 'hit_count=0 占比', icon: CircleClose, color: '#ef4444' },
    { label: '平均最高相似度', value: (ov?.avg_max_score ?? 0).toFixed(3), unit: 'cosine', icon: TrendCharts, color: '#10b981' },
    { label: 'Context p95 token', value: String(ov?.p95_context_tokens ?? 0), unit: `均值 ${Math.round(ov?.avg_context_tokens ?? 0)}`, icon: Coin, color: '#f59e0b' },
  ]
})

async function load() {
  const [{ data: ov }, { data: tr }] = await Promise.all([
    contextApi.overview(days.value),
    contextApi.trends(days.value),
  ])
  overview.value = ov
  series.value = tr.series
  renderAll()
}

function renderAll() {
  const ov = overview.value
  const s = series.value
  const dates = s.map((p) => p.date.slice(5))
  // 1. 相似度直方图
  histChart?.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 50, right: 16, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: (ov?.score_histogram ?? []).map((b) => b.lo.toFixed(1)), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar', barWidth: '70%',
      itemStyle: { color: '#22d3ee', borderRadius: [4, 4, 0, 0] },
      data: (ov?.score_histogram ?? []).map((b) => b.count),
    }],
  }, true)
  // 2. token 趋势(均值 + p95)
  tokenChart?.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 16, top: 20, bottom: 44 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' },
    series: [
      { name: '均值', type: 'line', smooth: true, itemStyle: { color: '#3b82f6' }, data: s.map((p) => p.avg_context_tokens ?? null) },
      { name: 'p95', type: 'line', smooth: true, itemStyle: { color: '#f43f5e' }, lineStyle: { type: 'dashed' }, data: s.map((p) => p.p95_context_tokens ?? null) },
    ],
  }, true)
  // 3. 组成占比堆叠面积
  const composeSeries = [
    { name: 'system', key: 'avg_system_tokens' as const, color: '#8b5cf6' },
    { name: 'history', key: 'avg_history_tokens' as const, color: '#3b82f6' },
    { name: 'tool', key: 'avg_tool_tokens' as const, color: '#f59e0b' },
  ]
  composeChart?.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 16, top: 20, bottom: 44 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' },
    series: composeSeries.map((c) => ({
      name: c.name, type: 'line' as const, stack: 'compose', smooth: true,
      areaStyle: { opacity: 0.35 }, itemStyle: { color: c.color },
      data: s.map((p) => p[c.key] ?? 0),
    })),
  }, true)
  // 4. 离线评测趋势(Recall@K / Precision@K)
  evalChart?.setOption({
    tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => (v == null ? '—' : Number(v).toFixed(3)) },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 50, right: 16, top: 20, bottom: 44 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', min: 0, max: 1 },
    series: [
      { name: 'Recall@K', type: 'line', connectNulls: true, itemStyle: { color: '#34d399' }, data: s.map((p) => p.recall_at_k ?? null) },
      { name: 'Precision@K', type: 'line', connectNulls: true, itemStyle: { color: '#ec4899' }, data: s.map((p) => p.precision_at_k ?? null) },
    ],
  }, true)
}

async function onRecycleQuery(query: string) {
  await contextApi.createEvalCase({ query })
  ElMessage.success('已回收为评测用例(期望文档可后续在库中补标)')
}

async function onRecycleEvent(eventId: string) {
  await contextApi.recycleEvalCase({ event_id: eventId })
  ElMessage.success('已回收为评测用例(source=online)')
}

async function onRunEval() {
  await ElMessageBox.confirm(
    '对 cx_eval_cases(enabled)跑一遍检索评测,结果写入 cx_metrics_daily(Recall@K / Precision@K 上板)。',
    '离线评测', { type: 'info' },
  )
  evalRunning.value = true
  try {
    const { data } = await contextApi.runEval()
    const r = data as { case_count: number; recall_at_k: number | null; precision_at_k: number | null }
    ElMessage.success(
      `评测完成:${r.case_count} 条用例,Recall@K=${r.recall_at_k ?? '—'},Precision@K=${r.precision_at_k ?? '—'}`,
    )
    await load()
  } finally {
    evalRunning.value = false
  }
}

async function onSaveStrategy() {
  const { data } = await contextApi.updateStrategy({
    strategy: strategyForm.strategy || undefined,
    size: strategyForm.size, overlap: strategyForm.overlap,
    top_k: strategyForm.top_k, threshold: strategyForm.threshold,
  })
  ElMessage.success(`策略已生效:${data.strategy}(切分参数变更需重建索引后生效)`)
  strategyDialog.value = false
}

onMounted(async () => {
  histChart = echarts.init(histRef.value!)
  tokenChart = echarts.init(tokenRef.value!)
  composeChart = echarts.init(composeRef.value!)
  evalChart = echarts.init(evalRef.value!)
  const all = () => [histChart, tokenChart, composeChart, evalChart].forEach((c) => c?.resize())
  window.addEventListener('resize', all)
  try {
    const { data } = await contextApi.getStrategy()
    Object.assign(strategyForm, data)
  } catch { /* 策略读取失败用默认值 */ }
  await load()
})
onUnmounted(() => {
  ;[histChart, tokenChart, composeChart, evalChart].forEach((c) => c?.dispose())
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 14px 16px; }
.stat-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #606266; }
.stat-value { margin-top: 8px; }
.stat-value .num { font-size: 26px; font-weight: 700; color: #1f2d3d; font-variant-numeric: tabular-nums; }
.stat-value .unit { font-size: 12px; color: #909399; margin-left: 4px; }
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.chart-card { padding: 14px 18px; }
.chart-title { font-size: 15px; font-weight: 600; color: #1f2d3d; }
.chart-sub { font-size: 12px; font-weight: 400; color: #909399; margin-left: 8px; }
.chart { height: 260px; margin-top: 8px; }
.lists-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.list-card { padding: 14px 18px; }
.list-card .el-table { margin-top: 8px; }
@media (max-width: 1200px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .charts-grid, .lists-grid { grid-template-columns: 1fr; }
}
</style>
