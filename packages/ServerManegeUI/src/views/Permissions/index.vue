<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">权限维护</h2>
        <div class="page-subtitle">
          两个维度绑定操作权限:职级批量绑定(超管/部门经理) / 个人单独绑定(高职级向下调整或部门经理);
          同一权限点个人绑定优先于职级绑定
        </div>
      </div>
    </div>

    <div class="page-card">
      <el-tabs v-model="tab">
        <!-- Tab 1: 职级批量绑定(超管或部门经理) -->
        <el-tab-pane v-if="auth.isSuper || auth.isManager" label="职级权限" name="joblevel">
          <div v-for="group in groups" :key="group.department.id" class="dept-group">
            <div class="dept-title">{{ group.department.name }}</div>
            <el-table :data="group.levels" v-loading="loadingMatrix" stripe>
              <el-table-column label="职级" min-width="140">
                <template #default="{ row }">
                  {{ row.jobLevel.name }}
                  <span class="rank-tip">rank {{ row.jobLevel.rank }}</span>
                </template>
              </el-table-column>
              <el-table-column v-for="p in points" :key="p.code" :label="p.name" min-width="130" align="center">
                <template #default="{ row }">
                  <el-checkbox v-model="draft[row.jobLevel.id][p.code]" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="110" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" :loading="savingLevel === row.jobLevel.id"
                    @click="saveLevel(group.department.id, row)">保存</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="tab-tip">勾选后整行保存,全量覆盖该职级的权限绑定;同职级用户批量继承。</div>
        </el-tab-pane>

        <!-- Tab 2: 个人单独绑定 -->
        <el-tab-pane label="个人权限" name="user">
          <div class="user-pick">
            <el-select v-model="pickedUserId" filterable placeholder="选择用户(仅职级低于自己的可调)" style="width: 320px" @change="loadUserConfig">
              <el-option v-for="u in adjustableUsers" :key="u.id" :value="u.id"
                :label="`${u.displayName || u.username}(${u.username}) · ${u.jobLevel?.name || '无职级'} · ${u.department?.name || '未分配'}`" />
            </el-select>
          </div>

          <template v-if="userConfig">
            <el-alert v-if="userConfig.user.isSuperAdmin" type="warning" :closable="false" show-icon
              title="超级管理员拥有全部权限,无需也无法通过绑定变更" class="super-alert" />
            <el-table v-else :data="overrideRows" stripe>
              <el-table-column label="权限点" min-width="150">
                <template #default="{ row }">{{ row.name }}</template>
              </el-table-column>
              <el-table-column label="职级继承" width="110" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.inherited ? 'success' : 'info'" size="small">
                    {{ row.inherited ? '已授予' : '未授予' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="个人绑定(优先于职级)" min-width="320">
                <template #default="{ row }">
                  <el-radio-group v-model="row.mode">
                    <el-radio value="inherit">继承职级</el-radio>
                    <el-radio value="allow">允许</el-radio>
                    <el-radio value="deny">拒绝</el-radio>
                  </el-radio-group>
                </template>
              </el-table-column>
              <el-table-column label="生效结果" width="110" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.effective ? 'success' : 'info'" size="small">
                    {{ row.effective ? '有权限' : '无权限' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="!userConfig.user.isSuperAdmin" class="user-save">
              <el-button type="primary" :loading="savingUser" @click="saveUser">保存个人绑定</el-button>
              <span class="tab-tip">「继承职级」表示删除个人绑定记录;「拒绝」可收掉职级继承来的权限。</span>
            </div>
          </template>
          <el-empty v-else description="请选择要配置的用户" :image-size="90" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  orgUserApi,
  permConfigApi,
  type DeptPermGroup,
  type PermPoint,
  type UserItem,
  type UserPermConfig,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const tab = ref<'joblevel' | 'user'>(auth.isSuper || auth.isManager ? 'joblevel' : 'user')
const points = ref<PermPoint[]>([])

// ---------- Tab 1: 按部门分组的职级矩阵 ----------
const groups = ref<DeptPermGroup[]>([])
const loadingMatrix = ref(false)
const savingLevel = ref<number | null>(null)
/** 勾选草稿: jobLevelId → code → checked */
const draft = reactive<Record<number, Record<string, boolean>>>({})

async function loadPoints() {
  const { data } = await permConfigApi.points()
  points.value = data
}

async function loadMatrix() {
  if (!auth.isSuper && !auth.isManager) return
  loadingMatrix.value = true
  try {
    const { data } = await permConfigApi.jobLevelMatrix()
    groups.value = data
    for (const group of data) {
      for (const row of group.levels) {
        draft[row.jobLevel.id] = Object.fromEntries(
          points.value.map((point) => [point.code, row.codes.includes(point.code)]),
        )
      }
    }
  } finally {
    loadingMatrix.value = false
  }
}

async function saveLevel(deptId: number, row: { jobLevel: { id: number; name: string; rank: number }; codes: string[] }) {
  savingLevel.value = row.jobLevel.id
  try {
    const codes = points.value.filter((p) => draft[row.jobLevel.id]?.[p.code]).map((p) => p.code)
    await permConfigApi.setJobLevelPerms(row.jobLevel.id, codes)
    ElMessage.success(`已保存「${row.jobLevel.name}」的权限绑定`)
    await loadMatrix()
  } finally {
    savingLevel.value = null
  }
}

// ---------- Tab 2: 个人绑定 ----------
const users = ref<UserItem[]>([])
const pickedUserId = ref('')
const userConfig = ref<UserPermConfig | null>(null)
const savingUser = ref(false)
interface OverrideRow {
  code: string; name: string
  inherited: boolean; mode: 'inherit' | 'allow' | 'deny'; effective: boolean
}
const overrideRows = ref<OverrideRow[]>([])

async function loadUsers() {
  const { data } = await orgUserApi.list()
  users.value = data
}

/**
 * 可调整的用户:超管本人不可修改,其余须职级严格低于当前操作者
 * 或属于操作者的部门子树(经理全权)。
 */
const adjustableUsers = computed(() => {
  if (auth.isSuper) return users.value.filter((u) => !u.isSuperAdmin)
  const myRank = auth.user?.jobLevel?.rank ?? Number.MAX_SAFE_INTEGER
  return users.value.filter((u) => {
    if (u.isSuperAdmin) return false
    // 经理全权: 同部门即可(不考虑 rank)
    if (auth.isManager && u.department?.id === auth.user?.department?.id) return true
    // 职级向下管理
    return (u.jobLevel?.rank ?? Number.MAX_SAFE_INTEGER) > myRank
  })
})

async function loadUserConfig() {
  if (!pickedUserId.value) {
    userConfig.value = null
    return
  }
  const { data } = await permConfigApi.userConfig(pickedUserId.value)
  userConfig.value = data
  const overrideMap = new Map(data.overrides.map((o) => [o.code, o.allowed]))
  const inheritedSet = new Set(data.inherited)
  const effectiveSet = new Set(data.effective)
  overrideRows.value = points.value.map((p) => {
    const ov = overrideMap.get(p.code)
    return {
      code: p.code,
      name: p.name,
      inherited: inheritedSet.has(p.code),
      mode: ov === undefined ? 'inherit' : ov ? 'allow' : 'deny',
      effective: effectiveSet.has(p.code),
    }
  })
}

async function saveUser() {
  savingUser.value = true
  try {
    const overrides = overrideRows.value.map((r) => ({
      code: r.code,
      allowed: r.mode === 'inherit' ? null : r.mode === 'allow',
    }))
    await permConfigApi.setUserPerms(pickedUserId.value, overrides)
    ElMessage.success('已保存个人权限绑定')
    await loadUserConfig()
  } finally {
    savingUser.value = false
  }
}

onMounted(async () => {
  await loadPoints()
  await Promise.all([loadMatrix(), loadUsers()])
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.rank-tip { font-size: 12px; color: #909399; margin-left: 6px; }
.tab-tip { font-size: 12px; color: #909399; margin-top: 10px; }
.user-pick { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.user-save { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.user-save .tab-tip { margin-top: 0; }
.super-alert { margin-bottom: 14px; }
.dept-group { margin-bottom: 18px; }
.dept-title { font-size: 15px; font-weight: 600; color: #1f2d3d; margin-bottom: 8px; }
.dept-group .el-table { margin-bottom: 0; }
</style>
