<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">限流熔断</h2>
        <div class="page-subtitle">令牌桶限流(QPM/TPM)与失败率熔断策略,全局 / 用户 / 渠道三维度</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openEdit()">新增策略</el-button>
    </div>

    <div class="page-card">
      <el-tabs v-model="tab" @tab-change="load">
        <el-tab-pane label="限流策略" name="RATE_LIMIT" />
        <el-tab-pane label="熔断策略" name="CIRCUIT_BREAKER" />
      </el-tabs>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="name" label="策略名称" min-width="150" />
        <el-table-column label="作用维度" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ { GLOBAL: '全局', USER: '用户', CHANNEL: '渠道' }[row.targetType as string] }}</el-tag>
            <span v-if="row.targetKey" class="target-key">{{ row.targetKey }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="tab === 'RATE_LIMIT'" label="规则" min-width="180">
          <template #default="{ row }">
            <span v-if="row.qpm">QPM ≤ {{ row.qpm }}</span>
            <span v-if="row.qpm && row.tpm"> · </span>
            <span v-if="row.tpm">TPM ≤ {{ row.tpm }}</span>
          </template>
        </el-table-column>
        <el-table-column v-else label="规则" min-width="220">
          <template #default="{ row }">
            {{ row.windowSeconds }}s 窗口失败率 ≥ {{ row.failureRateThreshold }}% → 熔断 {{ row.openSeconds }}s
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled === 1" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该策略?" @confirm="remove(row)">
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="editVisible" :title="form.id ? '编辑策略' : '新增策略'" width="480px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="策略名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type" :disabled="!!form.id">
            <el-radio value="RATE_LIMIT">限流</el-radio>
            <el-radio value="CIRCUIT_BREAKER">熔断</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="作用维度">
          <el-select v-model="form.targetType" style="width: 100%">
            <el-option label="全局" value="GLOBAL" />
            <el-option label="指定用户" value="USER" />
            <el-option label="指定渠道" value="CHANNEL" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.targetType === 'USER'" label="用户名">
          <el-input v-model="form.targetKey" placeholder="留空表示所有用户" />
        </el-form-item>
        <el-form-item v-if="form.targetType === 'CHANNEL'" label="渠道">
          <el-select v-model="form.targetKey" clearable placeholder="留空表示所有渠道" style="width: 100%">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <template v-if="form.type === 'RATE_LIMIT'">
          <el-form-item label="每分钟请求">
            <el-input-number v-model="form.qpm" :min="0" placeholder="0 表示不限制" />
          </el-form-item>
          <el-form-item label="每分钟令牌">
            <el-input-number v-model="form.tpm" :min="0" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="失败率阈值%">
            <el-input-number v-model="form.failureRateThreshold" :min="1" :max="100" />
          </el-form-item>
          <el-form-item label="统计窗口(秒)">
            <el-input-number v-model="form.windowSeconds" :min="10" />
          </el-form-item>
          <el-form-item label="熔断时长(秒)">
            <el-input-number v-model="form.openSeconds" :min="5" />
          </el-form-item>
        </template>

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
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { channelApi, policyApi, type Channel, type Policy } from '@/api'

const tab = ref<'RATE_LIMIT' | 'CIRCUIT_BREAKER'>('RATE_LIMIT')
const rows = ref<Policy[]>([])
const channels = ref<Channel[]>([])
const loading = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const form = reactive<Partial<Policy>>({})

async function load() {
  loading.value = true
  try {
    const { data } = await policyApi.list(tab.value)
    rows.value = data.data
  } finally {
    loading.value = false
  }
}

function openEdit(row?: Policy) {
  Object.keys(form).forEach((k) => delete (form as Record<string, unknown>)[k])
  Object.assign(form, row ? { ...row } : {
    name: '', type: tab.value, targetType: 'GLOBAL',
    qpm: 1000, failureRateThreshold: 50, windowSeconds: 60, openSeconds: 60, enabled: 1,
  })
  editVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form, enabled: form.enabled ?? 1 }
    if (form.id) {
      await policyApi.update(form.id, payload)
    } else {
      await policyApi.create(payload)
    }
    ElMessage.success('已保存')
    editVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggle(row: Policy) {
  await policyApi.update(row.id, { ...row, enabled: row.enabled === 1 ? 0 : 1 })
  load()
}

async function remove(row: Policy) {
  await policyApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  load()
  const { data } = await channelApi.list()
  channels.value = data.data
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.target-key { font-size: 12px; color: #909399; margin-left: 6px; }
</style>
