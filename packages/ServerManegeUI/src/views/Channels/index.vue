<template>
  <div>
    <div class="head-row">
      <div>
        <h2 class="page-title">渠道管理</h2>
        <div class="page-subtitle">
          模型提供方(渠道)接入点:地址、密钥、模型清单与调度优先级
        </div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openEdit()"
        >新增渠道</el-button
      >
    </div>

    <div class="channel-grid" v-loading="loading">
      <div
        v-for="ch in channels"
        :key="ch.id"
        class="channel-card"
        :class="{ disabled: ch.status === 0 }"
      >
        <div class="card-head">
          <div class="name">
            <span
              class="provider-dot"
              :style="{ background: providerColor(ch.provider) }"
            />
            {{ ch.name }}
          </div>
          <el-switch :model-value="ch.status === 1" @change="toggle(ch)" />
        </div>
        <div class="url">{{ ch.baseUrl }}</div>
        <div class="models">
          <el-tag
            v-for="m in parseModels(ch.models)"
            :key="m"
            size="small"
            class="model-tag"
            >{{ m }}</el-tag
          >
        </div>
        <div class="meta">
          <span>优先级 {{ ch.priority }}</span>
          <span>{{ ch.provider }}</span>
          <span>{{ ch.upstreamFormat || 'openai' }} / {{ ch.authType || 'bearer' }}</span>
          <span v-if="ch.enableSearch">联网搜索</span>
        </div>
        <div class="ops">
          <el-button link type="warning" size="small" :loading="fetchingId === ch.id" @click="openFetchResult(ch)">
            获取模型
          </el-button>
          <el-button link type="primary" size="small" @click="openEdit(ch)"
            >编辑</el-button
          >
          <el-popconfirm title="确认删除该渠道?" @confirm="remove(ch)">
            <template #reference>
              <el-button link type="danger" size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
      <el-empty
        v-if="!loading && !channels.length"
        description="暂无渠道,点击右上角新增"
      />
    </div>

    <el-dialog
      v-model="editVisible"
      :title="form.id ? '编辑渠道' : '新增渠道'"
      width="520px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="渠道名称" required>
          <el-input v-model="form.name" placeholder="如:公司模型 / 百炼模型" />
        </el-form-item>
        <el-form-item label="渠道 Key">
          <el-input
            v-model="form.channelKey"
            placeholder="如:company / bailian(调用方 X-Channel-Key 头按此路由)"
          />
        </el-form-item>
        <el-form-item label="提供方" required>
          <el-select v-model="form.provider" style="width: 100%">
            <el-option v-for="p in providers" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="上游格式">
          <el-select v-model="form.upstreamFormat" style="width: 100%">
            <el-option v-for="f in UPSTREAM_FORMATS" :key="f.value" :label="f.label" :value="f.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="认证字段">
          <el-select v-model="form.authType" style="width: 100%">
            <el-option v-for="a in AUTH_TYPES" :key="a.value" :label="a.label" :value="a.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口地址" required>
          <el-input
            v-model="form.baseUrl"
            placeholder="https://api.openai.com/v1"
          />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input
            v-model="form.apiKey"
            type="password"
            show-password
            placeholder="sk-..."
          />
        </el-form-item>
        <el-form-item label="模型列表" required>
          <div class="models-field">
            <el-select
              v-model="form.models"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="输入模型名后回车添加,或点击右侧按钮从上游获取"
              style="width: 100%"
            />
            <el-button
              size="small"
              type="primary"
              plain
              :loading="fetching"
              :disabled="!form.baseUrl || !form.apiKey"
              @click="fetchIntoForm"
            >获取模型列表</el-button>
          </div>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="100" />
          <span class="hint">数字越小越优先被调度</span>
        </el-form-item>
        <el-form-item label="联网搜索">
          <el-switch v-model="form.enableSearch" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save"
          >保存</el-button
        >
      </template>
    </el-dialog>

    <!-- 从上游获取到的模型列表(渠道卡片「获取模型」按钮) -->
    <el-dialog
      v-model="fetchVisible"
      :title="`上游模型列表 — ${fetchChannel?.name ?? ''}`"
      width="520px"
    >
      <div class="fetch-summary">
        从 <code>{{ fetchChannel?.baseUrl }}/models</code> 获取到
        {{ fetchedModels.length }} 个模型
      </div>
      <div class="fetch-models">
        <el-check-tag
          v-for="m in fetchedModels"
          :key="m"
          :checked="fetchSelected.includes(m)"
          class="fetch-tag"
          @change="toggleFetchSelected(m)"
          >{{ m }}</el-check-tag
        >
      </div>
      <el-alert
        v-if="fetchChannel"
        type="info"
        :closable="false"
        show-icon
        title="勾选后点「同步到渠道」,将覆盖该渠道当前模型列表"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="fetchVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!fetchSelected.length"
          :loading="applying"
          @click="applyFetched"
          >同步到渠道({{ fetchSelected.length }})</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Plus } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { channelApi, type Channel } from "@/api";

const providers = [
  "openai",
  "azure",
  "qwen",
  "deepseek",
  "moonshot",
  "zhipu",
  "ollama",
  "other",
];
/** 上游接口格式(决定请求协议约定;当前转发均为 OpenAI 兼容) */
const UPSTREAM_FORMATS = [
  { value: "openai", label: "openai(OpenAI 兼容)" },
  { value: "azure", label: "azure(Azure OpenAI)" },
  { value: "anthropic", label: "anthropic" },
  { value: "gemini", label: "gemini" },
  { value: "ollama", label: "ollama" },
  { value: "other", label: "other" },
];
/** 上游认证字段(API Key 放在请求的哪个位置) */
const AUTH_TYPES = [
  { value: "bearer", label: "Authorization: Bearer(OpenAI 默认)" },
  { value: "x-api-key", label: "x-api-key 头(Anthropic 风格)" },
  { value: "api-key", label: "api-key 头(Azure 风格)" },
  { value: "query", label: "URL 参数 ?api-key=(Azure 参数风格)" },
  { value: "none", label: "none(内网免认证)" },
];
const PROVIDER_COLORS: Record<string, string> = {
  openai: "#10a37f",
  azure: "#0078d4",
  qwen: "#615ced",
  deepseek: "#4d6bfe",
  moonshot: "#000",
  zhipu: "#3b5bfd",
  ollama: "#888",
  other: "#909399",
};

const channels = ref<Channel[]>([]);
const loading = ref(false);
const saving = ref(false);
const editVisible = ref(false);
const fetching = ref(false);
const fetchingId = ref("");
const fetchVisible = ref(false);
const applying = ref(false);
const fetchChannel = ref<Channel | null>(null);
const fetchedModels = ref<string[]>([]);
const fetchSelected = ref<string[]>([]);
const form = reactive({
  id: "",
  name: "",
  channelKey: "",
  provider: "openai",
  upstreamFormat: "openai",
  authType: "bearer",
  baseUrl: "",
  apiKey: "",
  models: [] as string[],
  enableSearch: false,
  priority: 10,
  remark: "",
});

function parseModels(json: string): string[] {
  try {
    return JSON.parse(json);
  } catch {
    return [];
  }
}
function providerColor(p: string) {
  return PROVIDER_COLORS[p] || PROVIDER_COLORS.other;
}

async function load() {
  loading.value = true;
  try {
    const { data } = await channelApi.list();
    channels.value = data.data;
  } finally {
    loading.value = false;
  }
}

function openEdit(ch?: Channel) {
  form.id = ch?.id || "";
  form.name = ch?.name || "";
  form.channelKey = ch?.channelKey || "";
  form.provider = ch?.provider || "openai";
  form.upstreamFormat = ch?.upstreamFormat || "openai";
  form.authType = ch?.authType || "bearer";
  form.baseUrl = ch?.baseUrl || "";
  form.apiKey = ch?.apiKey || "";
  form.models = ch ? parseModels(ch.models) : [];
  form.enableSearch = ch?.enableSearch || false;
  form.priority = ch?.priority ?? 10;
  form.remark = ch?.remark || "";
  editVisible.value = true;
}

/** 编辑对话框内:按当前填写的地址/Key/认证字段从上游拉模型列表,回填勾选框 */
async function fetchIntoForm() {
  fetching.value = true;
  try {
    const { data } = await channelApi.fetchModels({
      baseUrl: form.baseUrl,
      apiKey: form.apiKey,
      authType: form.authType,
    });
    // 并集回填:已手输的模型保留,新拉到的追加
    form.models = [...new Set([...form.models, ...data.data])];
    ElMessage.success(`获取到 ${data.data.length} 个模型,已回填`);
  } finally {
    fetching.value = false;
  }
}

/** 渠道卡片:用渠道已存的配置从上游拉模型列表,弹窗展示供选择性同步 */
async function openFetchResult(ch: Channel) {
  fetchingId.value = ch.id;
  try {
    const { data } = await channelApi.fetchModels({
      baseUrl: ch.baseUrl,
      apiKey: ch.apiKey,
      authType: ch.authType,
    });
    fetchChannel.value = ch;
    fetchedModels.value = data.data;
    // 默认勾选当前渠道已配置的模型,便于增量补充
    fetchSelected.value = parseModels(ch.models).filter((m) => data.data.includes(m));
    fetchVisible.value = true;
  } finally {
    fetchingId.value = "";
  }
}

function toggleFetchSelected(m: string) {
  const i = fetchSelected.value.indexOf(m);
  if (i >= 0) fetchSelected.value.splice(i, 1);
  else fetchSelected.value.push(m);
}

/** 把勾选的模型同步(覆盖)到渠道 models 并落库 */
async function applyFetched() {
  if (!fetchChannel.value || !fetchSelected.value.length) return;
  applying.value = true;
  try {
    const ch = fetchChannel.value;
    await channelApi.update(ch.id, {
      ...ch,
      models: fetchSelected.value,
    });
    ElMessage.success(`已同步 ${fetchSelected.value.length} 个模型到「${ch.name}」`);
    fetchVisible.value = false;
    load();
  } finally {
    applying.value = false;
  }
}

async function save() {
  if (!form.name || !form.baseUrl || !form.apiKey || !form.models.length) {
    ElMessage.warning("名称 / 地址 / Key / 模型列表为必填");
    return;
  }
  saving.value = true;
  try {
    const payload = { ...form, channelKey: form.channelKey || undefined };
    if (form.id) {
      await channelApi.update(form.id, payload);
    } else {
      await channelApi.create(payload);
    }
    ElMessage.success("已保存");
    editVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function toggle(ch: Channel) {
  await channelApi.changeStatus(ch.id, ch.status === 1 ? 0 : 1);
  load();
}

async function remove(ch: Channel) {
  await channelApi.remove(ch.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}
.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.channel-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 16px;
}
.channel-card.disabled {
  opacity: 0.55;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
  display: flex;
  align-items: center;
  gap: 8px;
}
.provider-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.url {
  font-size: 12px;
  color: #909399;
  margin: 8px 0;
  word-break: break-all;
}
.models {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 26px;
}
.model-tag {
  max-width: 100%;
}
.meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  margin-top: 10px;
}
.ops {
  border-top: 1px solid #f2f3f5;
  margin-top: 10px;
  padding-top: 6px;
  display: flex;
  justify-content: flex-end;
}
.hint {
  font-size: 12px;
  color: #c0c4cc;
  margin-left: 10px;
}
.models-field {
  display: flex;
  gap: 8px;
  width: 100%;
  align-items: flex-start;
}
.models-field .el-button {
  flex-shrink: 0;
}
.fetch-summary {
  font-size: 13px;
  color: #606266;
  margin-bottom: 10px;
}
.fetch-summary code {
  color: #8b5cf6;
}
.fetch-models {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}
.fetch-tag {
  cursor: pointer;
}
</style>
