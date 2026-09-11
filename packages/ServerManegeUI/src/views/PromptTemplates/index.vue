<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">Prompt 模板</h2>
        <div class="page-subtitle">模板版本化管理:激活即热更新,不动代码改提示词</div>
      </div>
      <div class="head-actions">
        <el-button type="primary" :icon="Plus" @click="createDialog = true">新建模板</el-button>
        <el-button :icon="Refresh" circle @click="loadTemplates" />
      </div>
    </div>

    <div class="layout-row">
      <!-- 左:分组 → 模板树 -->
      <div class="page-card tree-card">
        <el-input v-model="filterText" placeholder="搜索模板 key / 名称" :prefix-icon="Search" clearable size="small" />
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="{ label: 'label', children: 'children' }"
          :filter-node-method="filterNode"
          node-key="nodeKey"
          highlight-current
          default-expand-all
          class="tpl-tree"
          @node-click="onNodeClick"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon v-if="data.isGroup" :size="14"><Folder /></el-icon>
              <el-icon v-else :size="14"><Document /></el-icon>
              <span>{{ data.label }}</span>
              <el-tag v-if="!data.isGroup && data.tpl.status === 'disabled'" size="small" type="info">停用</el-tag>
              <el-tag v-else-if="!data.isGroup && data.tpl.current_version > 0" size="small" type="success">
                v{{ data.tpl.current_version }}
              </el-tag>
            </span>
          </template>
        </el-tree>
        <el-empty v-if="!treeData.length" description="暂无模板,点击右上角新建" :image-size="60" />
      </div>

      <!-- 右:编辑区 -->
      <div class="page-card editor-card" v-loading="loadingVersions">
        <template v-if="current">
          <div class="tpl-head">
            <div>
              <div class="tpl-key">
                {{ current.key }}
                <el-tag size="small" :type="current.status === 'active' ? 'success' : 'info'">
                  {{ current.status === 'active' ? '启用中' : '已停用(回退代码默认)' }}
                </el-tag>
              </div>
              <div class="tpl-desc">{{ current.name }} · {{ current.description || '无说明' }}</div>
            </div>
            <div class="tpl-actions">
              <el-button
                size="small" type="danger" plain
                :disabled="current.status === 'disabled'"
                @click="onDisable"
              >停用</el-button>
              <el-button
                size="small" type="danger" plain
                @click="onDeleteTemplate"
              >删除模板</el-button>
            </div>
          </div>

          <div class="ver-bar">
            <span class="ver-label">版本</span>
            <el-select v-model="selectedVersion" size="small" style="width: 260px" @change="onVersionChange">
              <el-option v-for="v in versions" :key="v.version" :value="v.version"
                :label="`v${v.version} (${v.status})${v.note ? ' — ' + v.note : ''}`">
                <span style="display: inline-flex; align-items: center; justify-content: space-between; width: 100%">
                  <span>v{{ v.version }} ({{ v.status }}){{ v.note ? ' — ' + v.note : '' }}</span>
                  <el-button v-if="v.status !== 'active'" link size="small" type="danger"
                    style="margin-left: 8px" @click.stop="onDeleteVersion(v.version)">删除</el-button>
                </span>
              </el-option>
            </el-select>
            <el-checkbox v-model="compareMode" size="small" :disabled="versions.length < 2">与激活版本对比</el-checkbox>
            <el-button size="small" type="primary" plain :icon="Promotion"
              :disabled="!selected || selected.status === 'active'"
              @click="onActivate">激活此版本</el-button>
          </div>

          <div v-if="compareMode && activeVersion" class="diff-wrap">
            <div class="diff-title">
              <span>v{{ activeVersion.version }}(激活)</span><span>v{{ selectedVersion }}(选中)</span>
            </div>
            <div class="diff-body">
              <div v-for="(line, i) in diffLines" :key="i" :class="['diff-line', line.type]">
                <span class="diff-sign">{{ line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' ' }}</span>
                <span v-html="highlightVars(escapeHtml(line.text))" />
              </div>
            </div>
          </div>
          <template v-else>
            <el-input
              v-model="editContent"
              type="textarea"
              :rows="14"
              class="editor-textarea"
              placeholder="模板文本,变量用 {{var}} 占位"
            />
            <div class="var-row">
              <span class="var-label">检测到变量:</span>
              <el-tag v-for="v in detectedVars" :key="v" size="small" effect="plain" class="var-tag">{{ v }}</el-tag>
              <span v-if="!detectedVars.length" class="var-none" v-text="'无(双花括号包裹变量名即变量占位)'" />
            </div>
            <div class="var-editor">
              <div class="var-editor-head">
                <span class="var-label">变量声明(用于模板装配提示)</span>
                <el-button size="small" :icon="Plus" @click="addVariable">添加变量</el-button>
              </div>
              <div v-for="(v, i) in editVariables" :key="v.name + i" class="var-form-row">
                <el-input v-model="v.name" size="small" placeholder="变量名" style="width: 140px" />
                <el-input v-model="v.desc" size="small" placeholder="说明" style="flex: 1" />
                <el-checkbox v-model="v.required" size="small">必填</el-checkbox>
                <el-button size="small" type="danger" plain :icon="Delete" @click="removeVariable(i)">删除</el-button>
              </div>
              <div v-if="!editVariables.length" class="var-none">暂无变量声明</div>
            </div>
            <div class="save-bar">
              <el-input v-model="saveNote" size="small" placeholder="版本说明(改了什么、为什么)" style="width: 320px" />
              <template v-if="selected?.status === 'draft'">
                <el-button size="small" type="primary" :icon="DocumentChecked" :disabled="!dirty && !varsDirty" @click="onUpdateVersion">
                  保存修改
                </el-button>
                <el-button size="small" type="primary" plain :icon="DocumentAdd" :disabled="!dirty" @click="onSaveVersion">
                  另存为新版本
                </el-button>
              </template>
              <el-button v-else size="small" type="primary" :icon="DocumentAdd" :disabled="!dirty" @click="onSaveVersion">
                保存为新版本
              </el-button>
            </div>
          </template>
        </template>
        <el-empty v-else description="从左侧选择一个模板" :image-size="80" />
      </div>
    </div>

    <!-- 新建模板对话框 -->
    <el-dialog v-model="createDialog" title="新建模板" width="560px">
      <el-form label-width="90px" size="default">
        <el-form-item label="标识 key" required>
          <el-input v-model="createForm.key" placeholder="如 agent.system / rag.search_docs / rules.xxx" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="展示名,如「Agent 系统提示词」" />
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="createForm.group" style="width: 100%">
            <el-option v-for="g in ['system', 'tool', 'judge', 'other']" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="createForm.description" placeholder="模板用途、影响面" />
        </el-form-item>
        <el-form-item label="初始内容">
          <el-input v-model="createForm.content" type="textarea" :rows="6" placeholder="v1 draft 内容,变量用 {{var}}" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!createForm.key || !createForm.name" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Refresh, Search, Folder, Document, DocumentAdd, DocumentChecked, Promotion, Delete,
} from '@element-plus/icons-vue'
import { promptApi, type PeTemplate, type PeVersion, type PeVariable } from '@/api'

interface TreeNode {
  nodeKey: string
  label: string
  isGroup: boolean
  tpl?: PeTemplate
  children?: TreeNode[]
}

const GROUP_NAMES: Record<string, string> = {
  system: '系统提示词', tool: '工具提示词', judge: '裁判提示词', other: '其他',
}

const templates = ref<PeTemplate[]>([])
const filterText = ref('')
const treeRef = ref()
const current = ref<PeTemplate | null>(null)
const versions = ref<PeVersion[]>([])
const loadingVersions = ref(false)
const selectedVersion = ref<number>()
const editContent = ref('')
const originalContent = ref('')
const editVariables = ref<PeVariable[]>([])
const originalVariables = ref<PeVariable[]>([])
const saveNote = ref('')
const compareMode = ref(false)
const createDialog = ref(false)
const createForm = reactive({ key: '', name: '', group: 'system', description: '', content: '' })

const treeData = computed<TreeNode[]>(() => {
  const groups = new Map<string, TreeNode>()
  for (const t of templates.value) {
    if (!groups.has(t.group)) {
      groups.set(t.group, { nodeKey: `g:${t.group}`, label: GROUP_NAMES[t.group] || t.group, isGroup: true, children: [] })
    }
    groups.get(t.group)!.children!.push({
      nodeKey: `t:${t.key}`, label: `${t.name} (${t.key})`, isGroup: false, tpl: t,
    })
  }
  return [...groups.values()]
})

const selected = computed(() => versions.value.find((v) => v.version === selectedVersion.value))
const activeVersion = computed(() => versions.value.find((v) => v.status === 'active'))
const dirty = computed(() => editContent.value !== originalContent.value)
const varsDirty = computed(() =>
  JSON.stringify(editVariables.value) !== JSON.stringify(originalVariables.value)
)
const detectedVars = computed(() => {
  const found = new Set<string>()
  for (const m of editContent.value.matchAll(/\{\{\s*(\w+)\s*\}\}/g)) found.add(m[1])
  return [...found]
})

/** 简单行级 diff(LCS):与激活版本对比,标注增删行 */
const diffLines = computed(() => {
  if (!compareMode.value || !activeVersion.value || !selected.value) return []
  const a = activeVersion.value.content.split('\n')
  const b = selected.value.content.split('\n')
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const lines: Array<{ type: 'same' | 'add' | 'del'; text: string }> = []
  let i = 0, j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { lines.push({ type: 'same', text: a[i] }); i++; j++ }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { lines.push({ type: 'del', text: a[i] }); i++ }
    else { lines.push({ type: 'add', text: b[j] }); j++ }
  }
  while (i < a.length) lines.push({ type: 'del', text: a[i++] })
  while (j < b.length) lines.push({ type: 'add', text: b[j++] })
  return lines
})

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
/** 模板文本里不能直接写 {{ }}(SFC 解析冲突),统一用函数拼 */
function wrapVar(name: string) {
  return '{{' + name + '}}'
}
function highlightVars(s: string) {
  return s.replace(/(\{\{\s*\w+\s*\}\})/g, '<span class="var-hl">$1</span>')
}

function filterNode(value: string, data: TreeNode) {
  if (!value) return true
  return data.isGroup || data.label.toLowerCase().includes(value.toLowerCase())
}
watch(filterText, (v) => treeRef.value?.filter(v))

async function loadTemplates() {
  const { data } = await promptApi.listTemplates()
  templates.value = data.templates
  if (current.value) {
    current.value = templates.value.find((t) => t.key === current.value!.key) ?? null
  }
}

async function onNodeClick(node: TreeNode) {
  if (node.isGroup || !node.tpl) return
  current.value = node.tpl
  compareMode.value = false
  loadingVersions.value = true
  try {
    const { data } = await promptApi.listVersions(node.tpl.key)
    versions.value = data.versions
    const active = data.versions.find((v) => v.status === 'active') ?? data.versions[0]
    selectedVersion.value = active?.version
    onVersionChange()
  } finally {
    loadingVersions.value = false
  }
}

function onVersionChange() {
  editContent.value = selected.value?.content ?? ''
  originalContent.value = editContent.value
  const vars = (selected.value?.variables ?? []).map((v) => ({ ...v }))
  editVariables.value = vars
  originalVariables.value = JSON.parse(JSON.stringify(vars))
  saveNote.value = ''
}

function addVariable() {
  editVariables.value.push({ name: '', desc: '', required: false })
}

function removeVariable(idx: number) {
  editVariables.value.splice(idx, 1)
}

async function onSaveVersion() {
  if (!current.value) return
  await promptApi.addVersion(current.value.key, {
    content: editContent.value,
    variables: editVariables.value.filter((v) => v.name.trim()),
    note: saveNote.value,
  })
  ElMessage.success('已保存为新版本(draft),激活后生效')
  saveNote.value = ''
  await onNodeClick({ nodeKey: '', label: '', isGroup: false, tpl: current.value })
}

async function onUpdateVersion() {
  if (!current.value || !selected.value) return
  await promptApi.updateVersion(current.value.key, selected.value.version, {
    content: editContent.value,
    variables: editVariables.value.filter((v) => v.name.trim()),
    note: saveNote.value || undefined,
  })
  ElMessage.success('已保存修改')
  saveNote.value = ''
  await onNodeClick({ nodeKey: '', label: '', isGroup: false, tpl: current.value })
}

async function onDeleteVersion(version: number) {
  if (!current.value) return
  try {
    await ElMessageBox.confirm(
      `删除 ${current.value.key} 的 v${version}?此操作不可恢复。`,
      '删除版本确认', { type: 'warning' },
    )
    await promptApi.deleteVersion(current.value.key, version)
    ElMessage.success('版本已删除')
    await onNodeClick({ nodeKey: '', label: '', isGroup: false, tpl: current.value })
  } catch {
    // 取消
  }
}

async function onDeleteTemplate() {
  if (!current.value) return
  try {
    await ElMessageBox.confirm(
      `删除模板 ${current.value.key}?(含所有版本)此操作不可恢复。`,
      '删除模板确认', { type: 'warning' },
    )
    await promptApi.deleteTemplate(current.value.key)
    ElMessage.success('模板已删除')
    current.value = null
    versions.value = []
    await loadTemplates()
  } catch {
    // 取消
  }
}

async function onActivate() {
  if (!current.value || !selected.value) return
  await ElMessageBox.confirm(
    `激活 ${current.value.key} 的 v${selected.value.version}?主链路立即热更新生效。`,
    '激活确认', { type: 'warning' },
  )
  await promptApi.activate(current.value.key, selected.value.version, saveNote.value || undefined)
  ElMessage.success('已激活,热更新生效')
  await loadTemplates()
  await onNodeClick({ nodeKey: '', label: '', isGroup: false, tpl: current.value })
}

async function onDisable() {
  if (!current.value) return
  await ElMessageBox.confirm(
    `停用 ${current.value.key}?主链路回退到代码内默认提示词。`,
    '停用确认', { type: 'warning' },
  )
  await promptApi.disable(current.value.key)
  ElMessage.success('已停用,回退代码默认')
  await loadTemplates()
}

async function onCreate() {
  try {
    await promptApi.createTemplate({ ...createForm })
    ElMessage.success('模板已创建(v1 draft)')
    createDialog.value = false
    Object.assign(createForm, { key: '', name: '', group: 'system', description: '', content: '' })
    await loadTemplates()
  } catch (e: unknown) {
    ElMessage.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '创建失败')
  }
}

nextTick(loadTemplates)
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; }
.layout-row { display: grid; grid-template-columns: 300px 1fr; gap: 12px; align-items: start; }
.tree-card { padding: 12px; min-height: 480px; }
.tpl-tree { margin-top: 10px; }
.tree-node { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.editor-card { padding: 16px 18px; min-height: 480px; }
.tpl-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.tpl-key { font-size: 16px; font-weight: 600; color: #1f2d3d; display: flex; align-items: center; gap: 8px; }
.tpl-desc { font-size: 12px; color: #909399; margin-top: 4px; }
.ver-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.ver-label { font-size: 13px; color: #606266; }
.editor-textarea :deep(textarea) { font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; }
.var-row { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.var-label { font-size: 12px; color: #909399; }
.var-tag { font-family: monospace; }
.var-none { font-size: 12px; color: #c0c4cc; }
.var-table { margin-top: 8px; border-top: 1px dashed #ebeef5; padding-top: 8px; }
.var-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #606266; padding: 2px 0; }
.var-item code { color: #8b5cf6; }
.save-bar { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.var-editor { margin-top: 10px; border-top: 1px dashed #ebeef5; padding-top: 10px; }
.var-editor-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.var-form-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.var-form-row .el-input { margin-right: 4px; }
.diff-wrap { border: 1px solid #ebeef5; border-radius: 6px; overflow: hidden; }
.diff-title { display: grid; grid-template-columns: 1fr 1fr; background: #f5f7fa; font-size: 12px; color: #606266; }
.diff-title span { padding: 6px 12px; }
.diff-body { max-height: 480px; overflow: auto; font-family: 'Consolas', monospace; font-size: 12.5px; }
.diff-line { display: flex; padding: 1px 8px; white-space: pre-wrap; word-break: break-all; }
.diff-sign { width: 16px; flex-shrink: 0; color: #b0b6c3; }
.diff-line.add { background: #f0f9eb; }
.diff-line.add .diff-sign { color: #67c23a; }
.diff-line.del { background: #fef0f0; text-decoration: line-through; color: #909399; }
.diff-line.del .diff-sign { color: #f56c6c; }
:deep(.var-hl) { color: #8b5cf6; font-weight: 600; }
</style>
