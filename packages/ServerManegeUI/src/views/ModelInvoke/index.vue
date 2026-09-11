<template>
  <div class="invoke-page">
    <div class="head-row">
      <div>
        <h2 class="page-title">模型调试台</h2>
        <div class="page-subtitle">通过网关向仓库渠道发起模型调用,限流/熔断/计量透明生效</div>
      </div>
      <div class="head-actions">
        <el-select v-model="model" placeholder="选择模型" style="width: 240px">
          <el-option-group v-for="ch in channels" :key="ch.id" :label="ch.name">
            <el-option v-for="m in parseModels(ch.models)" :key="ch.id + m" :label="m" :value="m" :disabled="ch.status === 0" />
          </el-option-group>
        </el-select>
        <el-button :icon="Delete" @click="messages = []">清空</el-button>
      </div>
    </div>

    <div class="page-card chat-card">
      <div ref="listRef" class="message-list">
        <div v-if="!messages.length" class="empty">
          <el-icon :size="40" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p>选择模型后开始对话;若渠道未配置真实 API Key,会返回上游错误</p>
        </div>
        <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
          <div class="bubble">
            <div class="role">{{ msg.role === 'user' ? '我' : msg.model || '助手' }}</div>
            <div class="content">{{ msg.content }}</div>
            <div v-if="msg.usage" class="usage">
              tokens: {{ msg.usage.prompt_tokens ?? 0 }} + {{ msg.usage.completion_tokens ?? 0 }}
              · {{ msg.durationMs }}ms
            </div>
          </div>
        </div>
        <div v-if="sending" class="message assistant">
          <div class="bubble"><div class="content typing">思考中…</div></div>
        </div>
      </div>

      <div class="input-row">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          placeholder="输入消息,Ctrl+Enter 发送"
          @keydown.ctrl.enter="send"
        />
        <el-button type="primary" :loading="sending" :disabled="!model || !input.trim()" @click="send">发送</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ChatDotRound, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { channelApi, invokeApi, type Channel } from '@/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  model?: string
  durationMs?: number
  usage?: { prompt_tokens?: number; completion_tokens?: number }
}

const channels = ref<Channel[]>([])
const model = ref('')
const input = ref('')
const messages = ref<ChatMessage[]>([])
const sending = ref(false)
const listRef = ref<HTMLDivElement>()

function parseModels(json: string): string[] {
  try { return JSON.parse(json) } catch { return [] }
}

async function send() {
  const text = input.value.trim()
  if (!text || !model.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  scrollBottom()
  const start = Date.now()
  try {
    const history = messages.value.slice(-10).map((m) => ({ role: m.role, content: m.content }))
    const { data } = await invokeApi.chat({ model: model.value, messages: history })
    const resp = data.data as {
      choices?: { message?: { content?: string } }[]
      usage?: { prompt_tokens?: number; completion_tokens?: number }
    }
    messages.value.push({
      role: 'assistant',
      content: resp.choices?.[0]?.message?.content || '(空响应)',
      model: model.value,
      durationMs: Date.now() - start,
      usage: resp.usage,
    })
  } catch {
    messages.value.push({ role: 'assistant', content: '调用失败,请检查渠道配置或限流/熔断策略', model: model.value })
    ElMessage.error('模型调用失败')
  } finally {
    sending.value = false
    scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

onMounted(async () => {
  const { data } = await channelApi.list()
  channels.value = data.data
  const first = channels.value.find((c) => c.status === 1)
  if (first) model.value = parseModels(first.models)[0] || ''
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.head-actions { display: flex; gap: 8px; }
.chat-card { display: flex; flex-direction: column; height: calc(100vh - 190px); }
.message-list { flex: 1; overflow-y: auto; padding: 8px 4px; }
.empty { text-align: center; color: #909399; margin-top: 120px; font-size: 13px; }
.message { display: flex; margin: 10px 0; }
.message.user { justify-content: flex-end; }
.bubble { max-width: 70%; background: #f4f6fa; border-radius: 10px; padding: 10px 14px; }
.message.user .bubble { background: #dbeafe; }
.role { font-size: 11px; color: #909399; margin-bottom: 4px; }
.content { font-size: 14px; color: #303133; white-space: pre-wrap; word-break: break-word; }
.typing { color: #909399; }
.usage { font-size: 11px; color: #b0b6c3; margin-top: 6px; }
.input-row { display: flex; gap: 10px; align-items: flex-end; border-top: 1px solid #f2f3f5; padding-top: 12px; }
</style>
