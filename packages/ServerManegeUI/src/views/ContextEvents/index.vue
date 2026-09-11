<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">检索与快照</h2>
        <div class="page-subtitle">检索事件流水与 Context 构成快照(观测记录,只读)</div>
      </div>
      <el-button :icon="Refresh" circle @click="reload" />
    </div>

    <el-tabs v-model="tab" class="page-card tabs-card" @tab-change="reload">
      <!-- ============ 检索事件 ============ -->
      <el-tab-pane label="检索事件" name="events">
        <div class="filter-row">
          <el-input v-model="eventFilter.user_id" placeholder="用户 ID" clearable size="small" style="width: 160px" @change="loadEvents(1)" />
          <el-input v-model="eventFilter.strategy" placeholder="策略标识" clearable size="small" style="width: 200px" @change="loadEvents(1)" />
          <el-checkbox v-model="eventFilter.zeroOnly" size="small" @change="loadEvents(1)">只看零结果</el-checkbox>
        </div>
        <el-table :data="events" size="small" v-loading="eventsLoading" row-key="id"
          @expand-change="(row: EventRow) => onExpand(row)">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-box" v-loading="row._detailLoading">
                <template v-if="row._detail">
                  <div v-if="row._detail.hits?.length" class="hits">
                    <div v-for="h in row._detail.hits" :key="h.chunk_id" class="hit-row">
                      <div class="hit-score">
                        <div class="hit-bar" :style="{ width: Math.max(4, h.score * 100) + '%' }" />
                        <span class="hit-num">{{ h.score.toFixed(3) }}</span>
                      </div>
                      <div class="hit-meta">
                        chunk <code>{{ h.chunk_id.slice(0, 8) }}…</code> · doc <code>{{ h.doc_id.slice(0, 8) }}…</code> · pos {{ h.position }}
                      </div>
                    </div>
                  </div>
                  <div v-else class="muted">零结果事件:候选最高分 {{ row.max_score.toFixed(3) }}(阈值 {{ row.threshold }}),可考虑回收为评测用例或调低阈值</div>
                </template>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="query" label="检索 query" min-width="220" show-overflow-tooltip />
          <el-table-column label="命中" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.hit_count > 0 ? 'success' : 'danger'">{{ row.hit_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最高分" width="90">
            <template #default="{ row }">{{ row.max_score.toFixed(3) }}</template>
          </el-table-column>
          <el-table-column prop="strategy" label="策略" width="180" show-overflow-tooltip />
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">{{ row.latency_ms }}ms</template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.hit_count === 0" size="small" type="warning" plain @click.stop="openRecycle(row)">
                回收为用例
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="eventPage"
          :total="eventTotal" :page-size="20" layout="total, prev, pager, next"
          class="pager" @current-change="loadEvents()" />
      </el-tab-pane>

      <!-- ============ Context 快照 ============ -->
      <el-tab-pane label="Context 快照" name="snapshots">
        <div class="filter-row">
          <el-input v-model="snapFilter.conversation_id" placeholder="会话 ID" clearable size="small" style="width: 220px" @change="loadSnapshots(1)" />
          <el-input v-model="snapFilter.user_id" placeholder="用户 ID" clearable size="small" style="width: 160px" @change="loadSnapshots(1)" />
          <el-checkbox v-model="snapFilter.ragOnly" size="small" @change="loadSnapshots(1)">只看含检索注入</el-checkbox>
        </div>
        <el-table :data="snapshots" size="small" v-loading="snapLoading" row-key="id">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-box">
                <div class="compose-bar">
                  <div class="seg system" :style="{ flexGrow: Math.max(row.system_tokens, 0.001) }">
                    system {{ row.system_tokens }}
                  </div>
                  <div class="seg history" :style="{ flexGrow: Math.max(row.history_tokens, 0.001) }">
                    history {{ row.history_tokens }}
                  </div>
                  <div class="seg tool" :style="{ flexGrow: Math.max(row.tool_tokens, 0.001) }">
                    tool {{ row.tool_tokens }}
                  </div>
                </div>
                <div class="expand-meta">
                  <span>三段为估算值(len/1.6);总计 {{ row.total_tokens >= 0 ? row.total_tokens : '未知' }} 取自模型 usage</span>
                  <span v-if="row.rag_chunk_ids.length">
                    注入 chunks:<code v-for="c in row.rag_chunk_ids" :key="c" class="chunk-code">{{ c.slice(0, 8) }}…</code>
                  </span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="会话" min-width="140">
            <template #default="{ row }"><code>{{ row.conversation_id ? row.conversation_id.slice(0, 12) + '…' : '(adhoc)' }}</code></template>
          </el-table-column>
          <el-table-column prop="model" label="模型" width="130" show-overflow-tooltip />
          <el-table-column label="总 token" width="100">
            <template #default="{ row }">{{ row.total_tokens >= 0 ? row.total_tokens : '—' }}</template>
          </el-table-column>
          <el-table-column prop="message_count" label="消息数" width="80" />
          <el-table-column label="RAG 注入" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.rag_injected ? 'success' : 'info'">{{ row.rag_injected ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="snapPage"
          :total="snapTotal" :page-size="20" layout="total, prev, pager, next"
          class="pager" @current-change="loadSnapshots()" />
      </el-tab-pane>
    </el-tabs>

    <!-- 回收为评测用例对话框 -->
    <el-dialog v-model="recycleDialog" title="回收为评测用例" width="520px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px"
        title="零结果 query 回收进 ground truth,标注期望命中的文档后可用于离线召回评测" />
      <el-form label-width="110px" size="default">
        <el-form-item label="query">
          <el-input :model-value="recycleTarget?.query" disabled />
        </el-form-item>
        <el-form-item label="期望文档 ID">
          <el-input v-model="recycleForm.expect_doc_ids" placeholder="逗号分隔,可留空待补标" />
        </el-form-item>
        <el-form-item label="应包含短语">
          <el-input v-model="recycleForm.expect_contains" placeholder="逗号分隔,可留空" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recycleDialog = false">取消</el-button>
        <el-button type="primary" @click="onRecycle">回收</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { Refresh } from '@element-plus/icons-vue'
import { contextApi, type ContextSnapshot, type RetrievalEvent } from '@/api'

type EventRow = RetrievalEvent & { _detail?: RetrievalEvent; _detailLoading?: boolean }

const tab = ref<'events' | 'snapshots'>('events')

const events = ref<EventRow[]>([])
const eventsLoading = ref(false)
const eventPage = ref(1)
const eventTotal = ref(0)
const eventFilter = reactive({ user_id: '', strategy: '', zeroOnly: false })

const snapshots = ref<ContextSnapshot[]>([])
const snapLoading = ref(false)
const snapPage = ref(1)
const snapTotal = ref(0)
const snapFilter = reactive({ conversation_id: '', user_id: '', ragOnly: false })

const recycleDialog = ref(false)
const recycleTarget = ref<EventRow | null>(null)
const recycleForm = reactive({ expect_doc_ids: '', expect_contains: '' })

function fmtTime(t?: string) {
  return t ? dayjs(t).format('MM-DD HH:mm:ss') : '—'
}

async function loadEvents(page?: number) {
  if (page) eventPage.value = page
  eventsLoading.value = true
  try {
    const { data } = await contextApi.retrievalEvents({
      page: eventPage.value, size: 20,
      user_id: eventFilter.user_id || undefined,
      strategy: eventFilter.strategy || undefined,
      zero_result: eventFilter.zeroOnly ? 1 : undefined,
    })
    events.value = data.events
    eventTotal.value = data.total
    // 展开行需要 hits 明细,行展开时按需拉详情
    for (const row of events.value) {
      row._detail = undefined
      row._detailLoading = false
    }
  } finally {
    eventsLoading.value = false
  }
}

async function loadSnapshots(page?: number) {
  if (page) snapPage.value = page
  snapLoading.value = true
  try {
    const { data } = await contextApi.snapshots({
      page: snapPage.value, size: 20,
      conversation_id: snapFilter.conversation_id || undefined,
      user_id: snapFilter.user_id || undefined,
      rag_injected: snapFilter.ragOnly ? 1 : undefined,
    })
    snapshots.value = data.snapshots
    snapTotal.value = data.total
  } finally {
    snapLoading.value = false
  }
}

function reload() {
  if (tab.value === 'events') loadEvents(1)
  else loadSnapshots(1)
}

function openRecycle(row: EventRow) {
  recycleTarget.value = row
  recycleForm.expect_doc_ids = ''
  recycleForm.expect_contains = ''
  recycleDialog.value = true
}

async function onRecycle() {
  if (!recycleTarget.value) return
  const split = (s: string) => s.split(/[,,\s]+/).map((x) => x.trim()).filter(Boolean)
  await contextApi.recycleEvalCase({
    event_id: recycleTarget.value.id,
    expect_doc_ids: split(recycleForm.expect_doc_ids),
    expect_contains: split(recycleForm.expect_contains),
  })
  ElMessage.success('已回收为评测用例(source=online),跑 eval retrieval 套件即生效')
  recycleDialog.value = false
}

// 行展开时懒加载 hits 明细
async function onExpand(row: EventRow) {
  if (row._detail || row._detailLoading) return
  row._detailLoading = true
  try {
    const { data } = await contextApi.retrievalEvent(row.id)
    row._detail = data
  } finally {
    row._detailLoading = false
  }
}

onMounted(() => loadEvents(1))
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.tabs-card { padding: 8px 18px 16px; }
.tabs-card :deep(.el-tabs__header) { margin-bottom: 12px; }
.filter-row { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.expand-box { padding: 10px 16px; }
.hits { display: flex; flex-direction: column; gap: 6px; max-width: 640px; }
.hit-row { display: flex; align-items: center; gap: 12px; }
.hit-score { width: 220px; height: 18px; background: #f2f3f5; border-radius: 4px; position: relative; flex-shrink: 0; }
.hit-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #67c23a, #409eff); }
.hit-num { position: absolute; right: 4px; top: 0; font-size: 11px; color: #606266; line-height: 18px; }
.hit-meta { font-size: 12px; color: #909399; }
.muted { color: #c0c4cc; font-size: 12px; }
.compose-bar { display: flex; height: 26px; border-radius: 4px; overflow: hidden; max-width: 640px; }
.seg { display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; min-width: 0; overflow: hidden; white-space: nowrap; }
.seg.system { background: #8b5cf6; }
.seg.history { background: #3b82f6; }
.seg.tool { background: #f59e0b; }
.expand-meta { display: flex; gap: 18px; margin-top: 8px; font-size: 12px; color: #909399; flex-wrap: wrap; }
.chunk-code { margin-left: 6px; color: #8b5cf6; }
</style>
