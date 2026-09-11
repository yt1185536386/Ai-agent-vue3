<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">用户管理</h2>
        <div class="page-subtitle">
          每个用户只属于一个部门;部门职位名额:经理 1 名 / 副经理 2 名 / 组长不限;上级只能管理下级
        </div>
      </div>
      <div class="head-actions">
        <el-input v-model="keyword" placeholder="用户名 / 昵称 / 邮箱" clearable style="width: 220px" />
        <el-button type="primary" :icon="Plus" @click="openEdit()">新增用户</el-button>
      </div>
    </div>

    <div class="page-card">
      <el-table :data="filtered" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" min-width="110" />
        <el-table-column prop="displayName" label="昵称" min-width="100" />
        <el-table-column prop="email" label="邮箱" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="部门" min-width="110">
          <template #default="{ row }">{{ row.department?.name || '未分配' }}</template>
        </el-table-column>
        <el-table-column label="部门职位" width="100">
          <template #default="{ row }">
            <el-tag :type="POSITION_TAG[row.deptPosition] || 'info'" size="small">
              {{ POSITION_TEXT[row.deptPosition] || row.deptPosition }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="职级" min-width="100">
          <template #default="{ row }">{{ row.jobLevel?.name || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="150">
          <template #default="{ row }">{{ row.lastLoginAt ? dayjs(row.lastLoginAt).format('YYYY-MM-DD HH:mm') : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <template v-if="!row.isSuperAdmin && row.id !== auth.user?.id">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-popconfirm title="确认删除该用户?" @confirm="remove(row)">
                <template #reference>
                  <el-button link type="danger" size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增 / 编辑用户 -->
    <el-dialog v-model="editVisible" :title="form.id ? '编辑用户' : '新增用户'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="!!form.id" placeholder="登录用户名(至少 3 位)" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.displayName" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item :label="form.id ? '重置密码' : '初始密码'" :required="!form.id">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="form.id ? '留空表示不修改' : '至少 6 位'" />
        </el-form-item>
        <el-form-item label="所属部门">
          <el-tree-select v-model="form.departmentId" :data="deptTree" check-strictly
            :render-after-expand="false" placeholder="选择部门" style="width: 100%"
            :props="{ label: 'name', value: 'id', children: 'children' }" />
        </el-form-item>
        <el-form-item label="部门职位">
          <el-select v-model="form.deptPosition" style="width: 100%">
            <el-option v-for="(text, key) in POSITION_TEXT" :key="key" :label="text" :value="key" />
          </el-select>
          <div class="form-tip">经理限 1 名 / 副经理限 2 名,名额超限后端会拒绝</div>
        </el-form-item>
        <el-form-item label="职级">
          <el-select v-model="form.jobLevelId" placeholder="缺省为部门最低职级" clearable style="width: 100%">
            <el-option v-for="l in deptJobLevels" :key="l.id" :label="`${l.name}(rank ${l.rank})`" :value="l.id" />
          </el-select>
          <div class="form-tip">职级按部门划分,只能选当前部门下的职级</div>
        </el-form-item>
        <el-form-item v-if="form.id" label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { deptApi, jobLevelApi, orgUserApi, type DeptNode, type JobLevelItem, type UserItem } from '@/api'
import { useAuthStore } from '@/stores/auth'

const POSITION_TEXT: Record<string, string> = {
  MANAGER: '经理', DEPUTY: '副经理', LEADER: '组长', MEMBER: '组员',
}
const POSITION_TAG: Record<string, 'danger' | 'warning' | 'primary' | 'info'> = {
  MANAGER: 'danger', DEPUTY: 'warning', LEADER: 'primary', MEMBER: 'info',
}

const auth = useAuthStore()
const users = ref<UserItem[]>([])
const departments = ref<DeptNode[]>([])
const jobLevels = ref<JobLevelItem[]>([])
const keyword = ref('')
const loading = ref(false)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return users.value
  return users.value.filter((u) =>
    [u.username, u.displayName, u.email].some((f) => f?.toLowerCase().includes(kw)),
  )
})

// ---------- 新增 / 编辑 ----------
const editVisible = ref(false)
const saving = ref(false)
const form = reactive({
  id: '',
  username: '',
  displayName: '',
  email: '',
  password: '',
  departmentId: null as number | null,
  deptPosition: 'MEMBER',
  jobLevelId: null as number | null,
  status: 1,
})

/** 当前表单所选部门可用的职级 */
const deptJobLevels = computed(() => {
  if (form.departmentId == null) return []
  return jobLevels.value
    .filter((l) => l.departmentId === form.departmentId)
    .sort((a, b) => a.rank - b.rank)
})

watch(
  () => form.departmentId,
  () => {
    if (form.jobLevelId != null && !deptJobLevels.value.some((l) => l.id === form.jobLevelId)) {
      form.jobLevelId = null
    }
  },
)

/** 扁平部门列表 → 树(el-tree-select 用) */
const deptTree = computed(() => {
  const nodes = departments.value.map((d) => ({ ...d, children: [] as DeptNode[] }))
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const roots: DeptNode[] = []
  for (const n of nodes) {
    const parent = n.parentId != null ? byId.get(n.parentId) : undefined
    if (parent) (parent as DeptNode & { children: DeptNode[] }).children.push(n)
    else roots.push(n)
  }
  return roots
})

async function load() {
  loading.value = true
  try {
    const [u, d, j] = await Promise.all([orgUserApi.list(), deptApi.list(), jobLevelApi.list()])
    users.value = u.data
    departments.value = d.data
    jobLevels.value = j.data
  } finally {
    loading.value = false
  }
}

function openEdit(row?: UserItem) {
  form.id = row?.id || ''
  form.username = row?.username || ''
  form.displayName = row?.displayName || ''
  form.email = row?.email || ''
  form.password = ''
  form.departmentId = row?.department?.id ?? null
  form.deptPosition = row?.deptPosition || 'MEMBER'
  form.jobLevelId = row?.jobLevel?.id ?? null
  form.status = row?.status ?? 1
  editVisible.value = true
}

async function save() {
  if (!form.id && (form.username.trim().length < 3 || form.password.length < 6)) {
    ElMessage.warning('用户名至少 3 位,初始密码至少 6 位')
    return
  }
  saving.value = true
  try {
    if (!form.id) {
      const body: Record<string, unknown> = {
        username: form.username.trim(),
        password: form.password,
        deptPosition: form.deptPosition,
        confirm: true,
      }
      if (form.displayName.trim()) body.displayName = form.displayName.trim()
      if (form.email.trim()) body.email = form.email.trim()
      if (form.departmentId != null) body.departmentId = form.departmentId
      if (form.jobLevelId != null) body.jobLevelId = form.jobLevelId
      await orgUserApi.create(body)
      ElMessage.success('已创建用户')
    } else {
      const row = users.value.find((u) => u.id === form.id)
      const body: Record<string, unknown> = { confirm: true }
      const lines: string[] = []
      if (form.displayName !== (row?.displayName || '')) { body.displayName = form.displayName; lines.push('昵称') }
      if (form.email !== (row?.email || '')) { body.email = form.email; lines.push('邮箱') }
      if (form.password) { body.newPassword = form.password; lines.push('重置密码') }
      if (form.departmentId != null && form.departmentId !== row?.department?.id) {
        body.departmentId = form.departmentId; lines.push('部门(调部门后职位缺省重置为组员)')
      }
      if (form.deptPosition !== row?.deptPosition) { body.deptPosition = form.deptPosition; lines.push('部门职位') }
      if (form.jobLevelId != null && form.jobLevelId !== row?.jobLevel?.id) {
        body.jobLevelId = form.jobLevelId; lines.push('职级')
      }
      if (form.status !== row?.status) { body.status = form.status; lines.push(form.status === 1 ? '启用' : '禁用') }
      if (lines.length) {
        await ElMessageBox.confirm(`确认修改: ${lines.join('、')}?`, '编辑用户', { type: 'warning' })
        await orgUserApi.update(form.id, body)
        ElMessage.success('已保存')
      }
    }
    editVisible.value = false
    await load()
  } catch (e) {
    // 取消确认或后端校验失败(错误消息已由 http 拦截器弹出)
    if (e === 'cancel' || e === 'close') return
  } finally {
    saving.value = false
  }
}

async function remove(row: UserItem) {
  await orgUserApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.4; margin-top: 4px; }
</style>
