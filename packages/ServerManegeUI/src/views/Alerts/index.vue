<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">告警中心</h2>
        <div class="page-subtitle">熔断 / 限流 / 失败率 / 时延异常告警,仅看板展示</div>
      </div>
      <div>
        <el-button v-if="tab === 'records'" @click="markAll">全部已读</el-button>
        <el-button v-else type="primary" :icon="Plus" @click="openEdit()">新增规则</el-button>
      </div>
    </div>

    <div class="page-card">
      <el-tabs v-model="tab">
        <el-tab-pane label="告警记录" name="records" />
        <el-tab-pane label="规则管理" name="rules" />
      </el-tabs>

      <!-- 告警记录 -->
      <template v-if="tab === 'records'">
        <div class="filter-row">
          <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="loadRecords(1)">
            <el-option label="告警中" value="FIRING" />
            <el-option label="已恢复" value="RESOLVED" />
          </el-select>
          <el-select v-model="query.severity" placeholder="级别" clearable style="width: 130px" @change="loadRecords(1)">
            <el-option label="严重" value="CRITICAL" />
            <el-option label="警告" value="WARN" />
            <el-option label="提示" value="INFO" />
          </el-select>
          <el-checkbox v-model="onlyUnread" @change="loadRecords(1)">仅未读</el-checkbox>
          <el-button :icon="Refresh" circle @click="loadRecords()" />
        </div>

        <el-table :data="records" v-loading="recordsLoading" stripe :row-class-name="rowClass">
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag :type="severityTag(row.severity)" size="small" effect="dark">
                {{ { CRITICAL: '严重', WARN: '警告', INFO: '提示' }[row.severity as string] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="告警内容" min-width="320" show-overflow-tooltip />
          <el-table-column prop="ruleName" label="触发规则" min-width="130" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'FIRING' ? 'danger' : 'success'" size="small" effect="plain">
                {{ row.status === 'FIRING' ? '告警中' : '已恢复' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发时间" width="165">
            <template #default="{ row }">{{ fmtTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.readFlag === 0" link type="primary" size="small" @click="markRead(row)">
                标记已读
              </el-button>
              <span v-else class="read-text">已读</span>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="query.page"
          :page-size="query.size"
          :total="total"
          layout="total, prev, pager, next"
          class="pager"
          @current-change="loadRecords()"
        />
      </template>

      <!-- 规则管理 -->
      <template v-else>
        <el-table :data="rules" v-loading="rulesLoading" stripe>
          <el-table-column prop="name" label="规则名称" min-width="140" />
          <el-table-column label="指标" width="130">
            <template #default="{ row }">
              <el-tag size="small">{{ METRIC_TEXT[row.metric] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="条件" min-width="200">
            <template #default="{ row }">
              <span v-if="row.metric === 'CIRCUIT_OPEN'">熔断打开即告警</span>
              <span v-else>{{ row.windowSeconds }}s 窗口内{{ METRIC_TEXT[row.metric] }} ≥ {{ row.threshold }}{{ METRIC_UNIT[row.metric] }}</span>
            </template>
          </el-table-column>
          <el-table-column label="作用维度" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.targetType === 'GLOBAL' ? '全局' : '渠道' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag :type="severityTag(row.severity)" size="small" effect="dark">
                {{ { CRITICAL: '严重', WARN: '警告', INFO: '提示' }[row.severity as string] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="静默期" width="90">
            <template #default="{ row }">{{ row.cooldownSeconds }}s</template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled === 1" @change="toggle(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-popconfirm title="确认删除该规则?历史告警记录会保留" @confirm="remove(row)">
                <template #reference>
                  <el-button link type="danger" size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>

    <!-- 规则编辑对话框 -->
    <el-dialog v-model="editVisible" :title="form.id ? '编辑规则' : '新增规则'" width="480px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="规则名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="告警指标">
          <el-select v-model="form.metric" style="width: 100%">
            <el-option v-for="(text, value) in METRIC_TEXT" :key="value" :label="text" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="作用维度">
          <el-select v-model="form.targetType" style="width: 100%">
            <el-option label="全局" value="GLOBAL" />
            <el-option label="指定渠道" value="CHANNEL" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.targetType === 'CHANNEL'" label="渠道">
          <el-select v-model="form.targetKey" clearable placeholder="留空表示所有渠道" style="width: 100%">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <template v-if="form.metric !== 'CIRCUIT_OPEN'">
          <el-form-item label="阈值">
            <el-input-number v-model="form.threshold" :min="0" />
            <span class="form-hint">{{ METRIC_UNIT[form.metric || ''] }}</span>
          </el-form-item>
          <el-form-item label="统计窗口(秒)">
            <el-input-number v-model="form.windowSeconds" :min="10" />
          </el-form-item>
        </template>
        <el-form-item label="静默期(秒)">
          <el-input-number v-model="form.cooldownSeconds" :min="0" />
        </el-form-item>
        <el-form-item label="告警级别">
          <el-radio-group v-model="form.severity">
            <el-radio value="INFO">提示</el-radio>
            <el-radio value="WARN">警告</el-radio>
            <el-radio value="CRITICAL">严重</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { alertApi, channelApi, type AlertRule, type AlertRecord, type Channel } from '@/api'

const METRIC_TEXT: Record<string, string> = {
  CIRCUIT_OPEN: '熔断打开',
  RATE_LIMIT_HIT: '限流命中',
  FAILURE_RATE: '失败率',
  AVG_LATENCY_MS: '平均时延',
  ERROR_COUNT: '错误次数',
}
const METRIC_UNIT: Record<string, string> = {
  CIRCUIT_OPEN: '',
  RATE_LIMIT_HIT: ' 次',
  FAILURE_RATE: '%',
  AVG_LATENCY_MS: ' ms',
  ERROR_COUNT: ' 次',
}

const tab = ref<'records' | 'rules'>('records')

// ---------- 告警记录 ----------
const records = ref<AlertRecord[]>([])
const recordsLoading = ref(false)
const total = ref(0)
const onlyUnread = ref(false)
const query = reactive({ status: '', severity: '', page: 1, size: 20 })

async function loadRecords(page?: number) {
  if (page) query.page = page
  recordsLoading.value = true
  try {
    const { data } = await alertApi.records({
      status: query.status || undefined,
      severity: query.severity || undefined,
      readFlag: onlyUnread.value ? 0 : undefined,
      page: query.page,
      size: query.size,
    })
    records.value = data.data
    total.value = data.total
  } finally {
    recordsLoading.value = false
  }
}

async function markRead(row: AlertRecord) {
  await alertApi.markRead(row.id)
  row.readFlag = 1
}

async function markAll() {
  await alertApi.markAllRead()
  ElMessage.success('已全部标记已读')
  loadRecords()
}

function rowClass({ row }: { row: AlertRecord }) {
  return row.readFlag === 0 ? 'unread-row' : ''
}

// ---------- 规则管理 ----------
const rules = ref<AlertRule[]>([])
const channels = ref<Channel[]>([])
const rulesLoading = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const form = reactive<Partial<AlertRule>>({})

async function loadRules() {
  rulesLoading.value = true
  try {
    const { data } = await alertApi.rules()
    rules.value = data.data
  } finally {
    rulesLoading.value = false
  }
}

function openEdit(row?: AlertRule) {
  Object.keys(form).forEach((k) => delete (form as Record<string, unknown>)[k])
  Object.assign(form, row ? { ...row } : {
    name: '', metric: 'FAILURE_RATE', targetType: 'GLOBAL',
    threshold: 50, windowSeconds: 60, cooldownSeconds: 300, severity: 'WARN', enabled: 1,
  })
  editVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form, enabled: form.enabled ?? 1 }
    if (form.id) {
      await alertApi.updateRule(form.id, payload)
    } else {
      await alertApi.createRule(payload)
    }
    ElMessage.success('已保存')
    editVisible.value = false
    loadRules()
  } finally {
    saving.value = false
  }
}

async function toggle(row: AlertRule) {
  await alertApi.updateRule(row.id, { ...row, enabled: row.enabled === 1 ? 0 : 1 })
  loadRules()
}

async function remove(row: AlertRule) {
  await alertApi.removeRule(row.id)
  ElMessage.success('已删除')
  loadRules()
}

// ---------- 工具 ----------
function severityTag(severity: string) {
  return severity === 'CRITICAL' ? 'danger' : severity === 'WARN' ? 'warning' : 'info'
}

function fmtTime(t: string) {
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

onMounted(async () => {
  loadRecords()
  loadRules()
  const { data } = await channelApi.list()
  channels.value = data.data
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.filter-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.read-text { font-size: 12px; color: #c0c4cc; }
.form-hint { margin-left: 8px; color: #909399; font-size: 12px; }
:deep(.unread-row) { background: #fef0f0; }
:deep(.unread-row:hover > td) { background: #fde2e2 !important; }
</style>
