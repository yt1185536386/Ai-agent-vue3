<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">调用日志</h2>
        <div class="page-subtitle">每一次模型调用的用量、耗时与结果</div>
      </div>
      <div class="head-actions">
        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          style="width: 340px"
          clearable
          @change="onFilter"
        />
        <el-input v-model="filters.username" placeholder="用户名" clearable style="width: 140px" @change="onFilter" />
        <el-input v-model="filters.model" placeholder="模型" clearable style="width: 160px" @change="onFilter" />
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 110px" @change="onFilter">
          <el-option label="成功" :value="1" />
          <el-option label="失败" :value="0" />
        </el-select>
      </div>
    </div>

    <div class="page-card">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="createdAt" label="时间" width="170">
          <template #default="{ row }">{{ dayjs(row.createdAt).format('YYYY-MM-DD HH:mm:ss') }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="140" show-overflow-tooltip />
        <el-table-column prop="channelName" label="渠道" width="110" />
        <el-table-column prop="model" label="模型" min-width="150" show-overflow-tooltip />
        <el-table-column label="方式" width="80">
          <template #default="{ row }">
            <el-tag :type="row.stream ? 'info' : 'primary'" size="small" effect="plain">
              {{ row.stream ? '流式' : '普通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Tokens" width="150">
          <template #default="{ row }">
            <span v-if="row.totalTokens != null">{{ row.promptTokens }} + {{ row.completionTokens }} = {{ row.totalTokens }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ row.durationMs != null ? `${row.durationMs}ms` : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="errorMessage" label="错误信息" min-width="160" show-overflow-tooltip />
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="size"
        layout="total, prev, pager, next"
        class="pager"
        @current-change="load"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { logApi, type InvokeLog } from '@/api'

const rows = ref<InvokeLog[]>([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)
const filters = reactive({ username: '', model: '', status: undefined as number | undefined })
/** 时间段过滤:[startTime, endTime],清空时为 null */
const timeRange = ref<[string, string] | null>(null)

/** 过滤条件变更:回到第一页再查 */
function onFilter() {
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const { data } = await logApi.page({
      page: page.value, size,
      username: filters.username || undefined,
      model: filters.model || undefined,
      status: filters.status,
      startTime: timeRange.value?.[0],
      endTime: timeRange.value?.[1],
    })
    rows.value = data.data
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
