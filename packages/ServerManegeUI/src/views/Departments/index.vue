<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">部门管理</h2>
        <div class="page-subtitle">
          部门树、成员职位与部门职级维护;每个部门:经理 1 名 + 副经理 2 名 + 组长若干 + 组员
        </div>
      </div>
      <el-button v-if="auth.hasPerm('dept:info') || auth.isSuper || auth.isManager" type="primary" :icon="Plus" @click="openDeptEdit()">新增根部门</el-button>
    </div>

    <div class="dept-layout">
      <!-- 左:部门树 -->
      <div class="page-card tree-card">
        <el-tree
          :data="deptTree"
          node-key="id"
          :props="{ label: 'name', children: 'children' }"
          :expand-on-click-node="false"
          default-expand-all
          highlight-current
          @node-click="(n: DeptNode) => (selectedId = n.id)"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <span>{{ data.name }}</span>
              <span v-if="auth.hasPerm('dept:info') || auth.isSuper || auth.isManager" class="tree-ops" @click.stop>
                <el-icon title="新增子部门" @click="openDeptEdit(data)"><Plus /></el-icon>
                <el-icon title="重命名" @click="openDeptEdit(data, true)"><Edit /></el-icon>
                <el-popconfirm v-if="data.parentId != null" title="确认删除该部门?" @confirm="removeDept(data)">
                  <template #reference>
                    <el-icon title="删除" @click.stop><Delete /></el-icon>
                  </template>
                </el-popconfirm>
              </span>
            </div>
          </template>
        </el-tree>
        <el-empty v-if="!deptTree.length" description="暂无部门" :image-size="80" />
      </div>

      <!-- 右:成员与职级 -->
      <div class="page-card member-card">
        <el-tabs v-if="selectedDept" v-model="activeTab" class="dept-tabs">
          <el-tab-pane label="成员职位" name="members">
            <div class="member-head">
              <div>
                <span class="member-title">{{ selectedDept.name }}</span>
                <span class="quota-tip">
                  经理 {{ quota.MANAGER }}/1 · 副经理 {{ quota.DEPUTY }}/2 · 组长 {{ quota.LEADER }} · 组员 {{ quota.MEMBER }}
                </span>
              </div>
            </div>
            <el-table :data="members" v-loading="loading" stripe>
              <el-table-column prop="username" label="用户名" min-width="110" />
              <el-table-column prop="displayName" label="昵称" min-width="100" />
              <el-table-column label="部门职位" width="120">
                <template #default="{ row }">
                  <el-tag :type="POSITION_TAG[row.deptPosition] || 'info'" size="small">
                    {{ POSITION_TEXT[row.deptPosition] || row.deptPosition }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="职级" min-width="100">
                <template #default="{ row }">{{ row.jobLevel?.name || '—' }}</template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                    {{ row.status === 1 ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column v-if="auth.hasPerm('dept:member') || auth.isManager" label="职位调整" width="150">
                <template #default="{ row }">
                  <el-select
                    v-if="!row.isSuperAdmin && row.id !== auth.user?.id"
                    :model-value="row.deptPosition"
                    size="small"
                    @change="(p: string) => changePosition(row, p)"
                  >
                    <el-option v-for="(text, key) in POSITION_TEXT" :key="key" :label="text" :value="key" />
                  </el-select>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="selectedDept && !loading && !members.length" description="该部门暂无成员" :image-size="80" />
          </el-tab-pane>

          <el-tab-pane label="职级管理" name="joblevels">
            <div class="member-head">
              <div>
                <span class="member-title">{{ selectedDept.name }} — 职级管理</span>
                <span class="quota-tip">每个部门一套职级,越小 rank 级别越高</span>
              </div>
              <el-button v-if="canEditJobLevels" type="primary" size="small" :icon="Plus" @click="openLevelEdit()">新增职级</el-button>
            </div>
            <el-table :data="deptJobLevels" v-loading="levelsLoading" stripe>
              <el-table-column prop="name" label="职级名称" min-width="140" />
              <el-table-column prop="rank" label="Rank" width="90" />
              <el-table-column label="内置" width="90" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.builtin" type="info" size="small">是</el-tag>
                  <span v-else>—</span>
                </template>
              </el-table-column>
              <el-table-column v-if="canEditJobLevels" label="操作" width="130" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openLevelEdit(row)">编辑</el-button>
                  <el-popconfirm title="确认删除该职级?" @confirm="removeLevel(row)">
                    <template #reference>
                      <el-button link type="danger" size="small">删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>

        <el-empty v-else description="请选择部门" :image-size="90" />
      </div>
    </div>

    <!-- 新增 / 重命名部门 -->
    <el-dialog v-model="deptVisible" :title="deptForm.id ? '重命名部门' : '新增部门'" width="420px">
      <el-form label-width="90px">
        <el-form-item v-if="!deptForm.id" label="父部门">
          <el-input :model-value="deptForm.parentName" disabled placeholder="根层级" />
        </el-form-item>
        <el-form-item label="部门名称" required>
          <el-input v-model="deptForm.name" placeholder="同一父部门下唯一" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptVisible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDept">保 存</el-button>
      </template>
    </el-dialog>

    <!-- 新增 / 编辑职级 -->
    <el-dialog v-model="levelVisible" :title="levelForm.id ? '编辑职级' : '新增职级'" width="420px">
      <el-form label-width="90px">
        <el-form-item label="所属部门">
          <el-input :model-value="selectedDept?.name" disabled />
        </el-form-item>
        <el-form-item label="职级名称" required>
          <el-input v-model="levelForm.name" placeholder="如 高级 / 中级 / 初级" />
        </el-form-item>
        <el-form-item label="Rank" required>
          <el-input-number v-model="levelForm.rank" :min="1" :precision="0" controls-position="right" />
          <div class="form-tip">数值越小级别越高(如 1 > 2)</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="levelVisible = false">取 消</el-button>
        <el-button type="primary" :loading="savingLevel" @click="saveLevel">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { deptApi, jobLevelApi, orgUserApi, type DeptNode, type JobLevelItem, type UserItem } from '@/api'
import { useAuthStore } from '@/stores/auth'

const POSITION_TEXT: Record<string, string> = {
  MANAGER: '经理', DEPUTY: '副经理', LEADER: '组长', MEMBER: '组员',
}
const POSITION_TAG: Record<string, 'danger' | 'warning' | 'primary' | 'info'> = {
  MANAGER: 'danger', DEPUTY: 'warning', LEADER: 'primary', MEMBER: 'info',
}

const auth = useAuthStore()
const departments = ref<DeptNode[]>([])
const users = ref<UserItem[]>([])
const allLevels = ref<JobLevelItem[]>([])
const loading = ref(false)
const levelsLoading = ref(false)
const selectedId = ref<number | null>(null)
const activeTab = ref<'members' | 'joblevels'>('members')

type DeptTreeNode = DeptNode & { children: DeptTreeNode[] }

const deptTree = computed<DeptTreeNode[]>(() => {
  const nodes = departments.value.map((d) => ({ ...d, children: [] as DeptTreeNode[] }))
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const roots: DeptTreeNode[] = []
  for (const n of nodes) {
    const parent = n.parentId != null ? byId.get(n.parentId) : undefined
    if (parent) parent.children.push(n)
    else roots.push(n)
  }
  return roots
})

const selectedDept = computed(() => departments.value.find((d) => d.id === selectedId.value) || null)
const members = computed(() =>
  selectedId.value == null ? [] : users.value.filter((u) => u.department?.id === selectedId.value),
)
const deptJobLevels = computed(() =>
  selectedId.value == null ? [] : allLevels.value.filter((l) => l.departmentId === selectedId.value).sort((a, b) => a.rank - b.rank),
)

/** 职级编辑权限:超管任意,部门经理限本部门(前端简单按当前选中部门判断,后端做严格子树校验) */
const canEditJobLevels = computed(() =>
  auth.isSuper || (auth.isManager && selectedDept.value?.id === auth.user?.department?.id),
)

const quota = computed(() => {
  const q = { MANAGER: 0, DEPUTY: 0, LEADER: 0, MEMBER: 0 } as Record<string, number>
  for (const m of members.value) q[m.deptPosition] = (q[m.deptPosition] ?? 0) + 1
  return q
})

async function load() {
  loading.value = true
  try {
    const [d, u, l] = await Promise.all([deptApi.list(), orgUserApi.list(), jobLevelApi.list()])
    departments.value = d.data
    users.value = u.data
    allLevels.value = l.data
    if (selectedId.value == null && departments.value.length) {
      selectedId.value = departments.value[0].id
    }
  } finally {
    loading.value = false
  }
}

watch(selectedId, () => {
  activeTab.value = 'members'
})

// ---------- 部门 CRUD ----------
const deptVisible = ref(false)
const saving = ref(false)
const deptForm = reactive({ id: null as number | null, parentId: null as number | null, parentName: '', name: '' })

function openDeptEdit(parent?: DeptNode, rename = false) {
  if (rename) {
    deptForm.id = parent!.id
    deptForm.name = parent!.name
  } else {
    deptForm.id = null
    deptForm.name = ''
  }
  deptForm.parentId = parent?.id ?? null
  deptForm.parentName = parent?.name || '根层级'
  deptVisible.value = true
}

async function saveDept() {
  if (!deptForm.name.trim()) {
    ElMessage.warning('请输入部门名称')
    return
  }
  saving.value = true
  try {
    if (deptForm.id) {
      await deptApi.update(deptForm.id, { name: deptForm.name.trim(), confirm: true })
      ElMessage.success('已重命名')
    } else {
      await deptApi.create({ name: deptForm.name.trim(), parentId: deptForm.parentId, confirm: true })
      ElMessage.success('已创建部门')
    }
    deptVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function removeDept(dept: DeptNode) {
  await deptApi.remove(dept.id)
  ElMessage.success('已删除')
  if (selectedId.value === dept.id) selectedId.value = null
  await load()
}

// ---------- 成员职位 ----------
async function changePosition(row: UserItem, position: string) {
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.displayName || row.username} 的部门职位调整为「${POSITION_TEXT[position]}」?`,
      '职位调整',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await orgUserApi.update(row.id, { deptPosition: position, confirm: true })
  ElMessage.success('已调整')
  await load()
}

// ---------- 职级 CRUD ----------
const levelVisible = ref(false)
const savingLevel = ref(false)
const levelForm = reactive({ id: null as number | null, name: '', rank: 1 })

function openLevelEdit(row?: JobLevelItem) {
  if (row) {
    levelForm.id = row.id
    levelForm.name = row.name
    levelForm.rank = row.rank
  } else {
    levelForm.id = null
    levelForm.name = ''
    levelForm.rank = 1
  }
  levelVisible.value = true
}

async function saveLevel() {
  if (!levelForm.name.trim()) {
    ElMessage.warning('请输入职级名称')
    return
  }
  if (!selectedDept.value) return
  savingLevel.value = true
  try {
    if (levelForm.id) {
      await jobLevelApi.update(levelForm.id, { name: levelForm.name.trim(), rank: levelForm.rank, confirm: true })
      ElMessage.success('已保存职级')
    } else {
      await jobLevelApi.create({
        name: levelForm.name.trim(),
        rank: levelForm.rank,
        departmentId: selectedDept.value.id,
        confirm: true,
      })
      ElMessage.success('已创建职级')
    }
    levelVisible.value = false
    await load()
  } finally {
    savingLevel.value = false
  }
}

async function removeLevel(row: JobLevelItem) {
  await jobLevelApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.dept-layout { display: flex; gap: 14px; align-items: flex-start; }
.tree-card { width: 300px; flex-shrink: 0; min-height: 300px; }
.member-card { flex: 1; min-width: 0; }
.tree-node { display: flex; align-items: center; justify-content: space-between; flex: 1; padding-right: 6px; }
.tree-ops { display: inline-flex; gap: 6px; color: #909399; }
.tree-ops .el-icon:hover { color: var(--gw-primary, #2563eb); }
.member-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.member-title { font-size: 15px; font-weight: 600; color: #1f2d3d; }
.quota-tip { margin-left: 12px; font-size: 12px; color: #909399; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.4; margin-top: 4px; }
.dept-tabs :deep(.el-tabs__content) { padding-top: 8px; }
</style>
