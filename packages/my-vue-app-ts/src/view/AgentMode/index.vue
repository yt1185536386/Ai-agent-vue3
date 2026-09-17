<template>
  <div class="layout">
    <!-- 左侧边栏:历史对话 + 新建对话(带滑入滑出动画) -->
    <Transition name="sidebar-slide">
      <aside v-if="!sidebarCollapsed" class="sidebar">
        <div class="sidebar-body">
          <div class="brand">
            <span class="brand-name">Eric agent</span>
            <div class="brand-actions">
              <button class="icon-btn" title="搜索">
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
              </button>
              <button
                class="icon-btn"
                title="收起侧栏"
                @click="sidebarCollapsed = true"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <rect x="3" y="4" width="18" height="16" rx="2" />
                  <path d="M9 4v16" />
                </svg>
              </button>
            </div>
          </div>

          <button class="new-chat" @click="newChat">
            <svg
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            新建对话
          </button>

          <nav class="menu">
            <button class="menu-item">
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M3 9a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                />
              </svg>
              我的空间
            </button>
            <!-- 模型来源:点击弹出来源列表,点击切换 -->
            <div class="menu-item-wrap">
              <button
                ref="providerBtn"
                class="menu-item"
                @click="toggleProviderMenu"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="m12 2 9 5-9 5-9-5z" />
                  <path d="m3 12 9 5 9-5" />
                  <path d="m3 17 9 5 9-5" />
                </svg>
                模型来源
                <span class="provider-tag">{{ currentProviderName }}</span>
              </button>
              <ul
                v-if="providerMenuOpen"
                class="attach-menu provider-menu"
                :style="providerMenuStyle"
              >
                <li
                  v-for="p in providers"
                  :key="p.key"
                  :class="[
                    'attach-menu-item',
                    { active: p.key === currentProvider },
                  ]"
                  @click="selectProvider(p.key)"
                >
                  <span>{{ p.name }}</span>
                  <svg
                    v-if="p.key === currentProvider"
                    viewBox="0 0 24 24"
                    width="15"
                    height="15"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                </li>
              </ul>
            </div>
          </nav>
          <div
            v-if="providerMenuOpen"
            class="dropdown-overlay"
            @click="providerMenuOpen = false"
          ></div>

          <div class="section-label">最近对话</div>
          <ul class="conv-list">
            <li
              v-for="c in conversations"
              :key="c.id"
              :class="['conv-item', { active: c.id === activeId }]"
              @click="selectConv(c.id)"
            >
              <span class="conv-title">{{ c.title }}</span>
              <button
                class="conv-del"
                title="删除"
                @click.stop="removeConv(c.id)"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </li>
          </ul>
        </div>

        <div class="sidebar-user">
          <!-- 用户区域:点击弹出用户菜单 -->
          <div class="user-profile" @click="toggleUserMenu">
            <img
              class="avatar"
              src="../../assets/Ericicon/icon1.png"
              :alt="auth?.username || '用户'"
            />
            <span class="username">{{ auth?.username || '未登录' }}</span>
          </div>
          <div v-if="userMenuOpen" class="user-popup">
            <div class="user-item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              设置
            </div>
            <div class="user-item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 7v6m0 0-3-3m3 3 3-3"/><path d="M8 21h8"/></svg>
              客户端下载
            </div>
            <div class="user-item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
              深色模式
            </div>
            <div class="user-item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13a8 8 0 0 1 16 0"/><rect x="3" y="13" width="4" height="6" rx="2"/><rect x="17" y="13" width="4" height="6" rx="2"/><path d="M20 19a3 3 0 0 1-3 3h-3"/></svg>
              客服中心
            </div>
            <div class="user-item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 9-4 3 4 3"/><path d="m16 9 4 3-4 3"/><path d="m13 6-2 12"/></svg>
              API 服务
            </div>
            <div v-if="isLoggedIn" class="user-item" @click="logout">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>
              退出登录
            </div>
            <div v-else class="user-item" @click="goLogin">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/></svg>
              用户登录
            </div>
          </div>
          <!-- 关于信息:感叹号固定在最右侧,点击开启/关闭弹窗 -->
          <div class="info-wrap">
            <button class="info-btn" title="关于" @click="toggleInfo">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16.5h.01"/></svg>
            </button>
            <div v-if="infoOpen" class="info-popup">
              <div class="info-item">联系我们</div>
              <div class="info-item">用户协议</div>
              <div class="info-item">隐私政策</div>
              <div class="info-item">侵权投诉</div>
              <div class="info-footer">
                Eric agent 团队出品<br />
                内部工具,仅限学习交流使用<br />
                联系我们:eric_yang@example.com
              </div>
            </div>
          </div>
        </div>
        <!-- 点击弹窗外任意处关闭 -->
        <div
          v-if="infoOpen"
          class="dropdown-overlay"
          @click="infoOpen = false"
        ></div>
        <div
          v-if="userMenuOpen"
          class="dropdown-overlay"
          @click="userMenuOpen = false"
        ></div>
      </aside>
    </Transition>

    <!-- 右侧:对话内容窗口 -->
    <main class="main">
      <header class="main-header">
        <!-- 侧栏收起时:在内容区显示展开和新建会话按钮 -->
        <template v-if="sidebarCollapsed">
          <button
            class="icon-btn"
            title="展开侧栏"
            @click="sidebarCollapsed = false"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M9 4v16" />
            </svg>
          </button>
          <button class="icon-btn" title="新建对话" @click="newChat">
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
            </svg>
          </button>
        </template>
        <div class="model-select">
          <button class="model-switch" @click="toggleDropdown">
            {{ currentModel || "加载中..." }} · Eric agent
            <svg
              viewBox="0 0 24 24"
              width="14"
              height="14"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          <ul v-if="showDropdown" class="model-dropdown">
            <!-- 搜索框:吸顶,模型多时按名称过滤 -->
            <li class="model-search" @click.stop>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
              <input
                v-model="modelFilter"
                type="text"
                placeholder="搜索模型"
                @keydown.stop
              />
            </li>
            <li v-if="models.length === 0" class="model-option empty">
              暂无可用模型
            </li>
            <li v-else-if="filteredModels.length === 0" class="model-option empty">
              无匹配模型
            </li>
            <li
              v-for="m in filteredModels"
              :key="m"
              :class="['model-option', { active: m === currentModel }]"
              @click="selectModel(m)"
            >
              <span class="model-name">{{ m }}</span>
              <svg
                v-if="m === currentModel"
                viewBox="0 0 24 24"
                width="15"
                height="15"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </li>
          </ul>
        </div>
      </header>
      <div
        v-if="showDropdown"
        class="dropdown-overlay"
        @click="showDropdown = false"
      ></div>
      <div
        v-if="attachMenuOpen"
        class="dropdown-overlay"
        @click="attachMenuOpen = false"
      ></div>

      <!-- 隐藏的文件选择框 -->
      <input
        ref="docInput"
        type="file"
        hidden
        multiple
        accept=".pdf,.doc,.docx,.txt,.md,.csv,.xls,.xlsx,.ppt,.pptx"
        @change="onPick($event, 'doc')"
      />
      <input
        ref="imgInput"
        type="file"
        hidden
        multiple
        accept="image/*"
        @change="onPick($event, 'image')"
      />

      <div ref="msgBox" class="messages" @scroll="updateNavActive">
        <div
          v-for="(msg, index) in activeMessages"
          :key="index"
          :class="['msg-row', msg.role]"
        >
          <div class="msg-col">
            <div :class="['bubble', { 'error-bubble': msg.error }]">
              <div v-if="msg.attachments?.length" class="msg-attach-list">
                <template v-for="(att, i) in msg.attachments" :key="i">
                  <img
                    v-if="att.type === 'image'"
                    :src="att.url"
                    :alt="att.name"
                    class="msg-attach-thumb clickable"
                    @click="previewImage = att.url"
                  />
                  <span v-else class="msg-attach-file">
                    <svg
                      viewBox="0 0 24 24"
                      width="14"
                      height="14"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                      />
                      <path d="M14 2v6h6" />
                    </svg>
                    {{ att.name }}
                  </span>
                </template>
              </div>
              <!-- 思考过程(reasoning SSE 事件):思考一开始默认展开,思考结束自动收起;
                   思考进行中标题显示动态提示,告知用户正文需等思考完成才生成 -->
              <details
                v-if="msg.reasoning"
                class="reasoning"
                :open="msg.reasoningOpen"
              >
                <summary>
                  <svg
                    v-if="msg.reasoningStreaming"
                    viewBox="0 0 24 24" width="12" height="12" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round"
                    stroke-linejoin="round" class="tool-spin reasoning-spin"
                  >
                    <path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="m16.24 7.76 2.83-2.83"/>
                  </svg>
                  <span v-if="msg.reasoningStreaming" class="reasoning-hint">
                    深度思考中…正文将在思考完成后生成
                  </span>
                  <template v-else>思考过程</template>
                </summary>
                <div class="reasoning-body">{{ msg.reasoning }}</div>
              </details>
              <span v-if="msg.loading" class="typing"
                ><i></i><i></i><i></i
              ></span>
              <!-- 工具调用步骤(tool_start/tool_end 事件):主流的可折叠步骤列表,
                   进行中自动展开+转圈,审批暂停显示⏸,全部完成自动收起 -->
              <details
                v-if="msg.toolSteps?.length"
                class="tool-steps"
                :open="msg.toolStepsOpen"
              >
                <summary>
                  <svg
                    v-if="toolStepsRunning(msg)"
                    viewBox="0 0 24 24" width="13" height="13" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round"
                    stroke-linejoin="round" class="tool-spin"
                  >
                    <path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="m16.24 7.76 2.83-2.83"/>
                  </svg>
                  <span v-else class="tool-wrench">🔧</span>
                  {{ toolStepSummary(msg) }}
                </summary>
                <div class="tool-steps-body">
                  <div
                    v-for="(s, si) in msg.toolSteps"
                    :key="si"
                    class="tool-step"
                  >
                    <span
                      :class="['tool-step-icon', `is-${s.status}`]"
                      :title="s.status === 'running' ? '进行中' : s.status === 'paused' ? '等待审批' : '已完成'"
                    >
                      <svg
                        v-if="s.status === 'running'"
                        viewBox="0 0 24 24" width="12" height="12" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round"
                        stroke-linejoin="round" class="tool-spin"
                      >
                        <path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="m16.24 7.76 2.83-2.83"/>
                      </svg>
                      <template v-else-if="s.status === 'paused'">⏸</template>
                      <template v-else>✓</template>
                    </span>
                    <span class="tool-step-name">{{ s.name }}</span>
                    <span class="tool-step-args">{{ toolArgsSummary(s) }}</span>
                    <div v-if="s.result" class="tool-step-result">
                      {{ s.result }}
                    </div>
                  </div>
                </div>
              </details>
              <!-- assistant 的文字内容:与工具步骤独立渲染(工具调用和正文可同时存在),
                   不能用 v-else-if 挂在 toolSteps 后面,否则有工具调用的回复正文永远不显示 -->
              <template v-if="msg.role === 'assistant'">
                <!-- 后端标识或实时判定为 markdown 的回复:用 Markdown 渲染(图片点击可放大) -->
                <div
                  v-if="shouldRenderMarkdown(msg)"
                  class="markdown-body"
                  v-html="renderMarkdown(msg.content)"
                  @click="onMarkdownClick"
                ></div>
                <template v-else>
                  <template
                    v-for="(seg, si) in renderSegments(msg.content)"
                    :key="si"
                  >
                    <img
                      v-if="seg.type === 'image'"
                      :src="seg.url"
                      :alt="seg.alt"
                      class="msg-attach-thumb clickable"
                      @click="previewImage = seg.url"
                    />
                    <template v-else>{{ seg.text }}</template>
                  </template>
                </template>
              </template>
              <template v-else>{{ msg.content }}</template>
              <!-- HITL 审批卡片(approval_request 事件):写操作暂停,等待批准/拒绝 -->
              <div v-if="msg.approval?.items?.length" class="approval-card">
                <div class="approval-title">
                  ⚠️ 以下操作已暂停,等待你的审批:
                </div>
                <ul class="approval-list">
                  <li v-for="(item, ii) in msg.approval.items" :key="ii">
                    <span class="ap-action">{{ item.value?.action || "操作" }}</span>
                    {{ item.value?.detail }}
                  </li>
                </ul>

                <!-- 交互式审批:职级选择 + 理由填写(仅当 item.value.jobLevels 存在) -->
                <div
                  v-for="(item, ii) in msg.approval.items"
                  v-if="item.value?.jobLevels?.length"
                  :key="'form-' + ii"
                  class="approval-form"
                >
                  <div class="form-row">
                    <label class="form-label">目标职级</label>
                    <select
                      class="form-select"
                      :value="approvalSelections.get(item.id)?.jobLevelId ?? item.value?.jobLevelId ?? ''"
                      @change="(e) => {
                        const v = Number(e.target.value) || null;
                        approvalSelections.set(item.id, {
                          ...(approvalSelections.get(item.id) || {}),
                          jobLevelId: v,
                        });
                      }"
                    >
                      <option value="" disabled>请选择职级</option>
                      <option
                        v-for="jl in item.value.jobLevels"
                        :key="jl.id"
                        :value="jl.id"
                      >
                        {{ jl.name }}(rank {{ jl.rank }})
                      </option>
                    </select>
                  </div>
                  <div class="form-row">
                    <label class="form-label">调整理由</label>
                    <textarea
                      class="form-textarea"
                      rows="2"
                      placeholder="请填写调整理由(可选)"
                      :value="approvalSelections.get(item.id)?.reason ?? ''"
                      @input="(e) => {
                        approvalSelections.set(item.id, {
                          ...(approvalSelections.get(item.id) || {}),
                          reason: e.target.value,
                        });
                      }"
                    />
                  </div>
                  <div class="approval-actions">
                    <button
                      class="ap-approve"
                      @click="submitApprovalWithOptions(msg, item, 'approve')"
                    >
                      确认调整
                    </button>
                    <button
                      class="ap-reject"
                      @click="submitApprovalWithOptions(msg, item, 'reject')"
                    >
                      拒绝
                    </button>
                  </div>
                </div>

                <!-- 简单审批:无交互字段时保持原样 -->
                <div
                  v-if="!msg.approval.items.some((i) => i.value?.jobLevels?.length)"
                  class="approval-actions"
                >
                  <button class="ap-approve" @click="submitApproval(msg, 'approve')">
                    批准执行
                  </button>
                  <button class="ap-reject" @click="submitApproval(msg, 'reject')">
                    拒绝
                  </button>
                </div>
              </div>
            </div>
            <div v-if="!msg.loading" class="msg-actions">
              <button
                class="action-btn"
                :title="copiedIndex === index ? '已复制' : '复制'"
                @click="copyMessage(msg, index)"
              >
                <svg
                  v-if="copiedIndex !== index"
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="9" y="9" width="12" height="12" rx="2" />
                  <path d="M5 15V5a2 2 0 0 1 2-2h10" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </button>
              <button
                v-if="msg.role === 'assistant' && index > 0"
                class="action-btn"
                title="重新生成"
                @click="regenerate(index)"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                  <path d="M21 3v6h-6" />
                </svg>
              </button>
              <button
                v-if="msg.role === 'user'"
                class="action-btn"
                :disabled="isLoading"
                :title="isLoading ? '回答生成中,暂不可重发' : '重发'"
                @click="resendMessage(msg)"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="m22 2-7 20-4-9-9-4z" />
                  <path d="M22 2 11 13" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧消息导航:仅标记用户提问位置,悬浮显示提问预览,点击跳转 -->
      <div
        v-if="navItems.length > 1"
        class="msg-nav"
        @mouseenter="openNav"
        @mouseleave="navOpen = false"
      >
        <span
          v-for="item in navItems"
          :key="item.index"
          class="nav-dash"
          :style="{ top: item.top + '%' }"
        ></span>
        <div v-if="navOpen" class="nav-panel">
          <div
            v-for="item in navItems"
            :key="item.index"
            :class="['nav-item', { active: item.index === navActiveIndex }]"
            @click="jumpTo(item.index)"
          >
            {{ item.preview }}
          </div>
        </div>
      </div>

      <div
        :class="['composer-wrap', { centered: activeMessages.length === 0 }]"
      >
        <!-- 空对话欢迎语:与输入框同一容器,整体垂直居中,不会重叠 -->
        <div v-if="activeMessages.length === 0" class="welcome">
          <img
            class="welcome-logo"
            src="../../assets/Ericicon/icon1.png"
            alt="logo"
          />
          <span class="welcome-text">你好,我是 Eric agent</span>
        </div>
        <div :class="['composer', { disabled: isLoading }]">
          <!-- 附件预览区 -->
          <div v-if="attachments.length" class="attach-list">
            <div v-for="(att, i) in attachments" :key="i" class="attach-item">
              <img
                v-if="att.type === 'image'"
                :src="att.url"
                :alt="att.name"
                :class="['attach-thumb', { uploading: att.uploading }]"
              />
              <div v-else class="attach-file">
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                  />
                  <path d="M14 2v6h6" />
                </svg>
                <span class="attach-name">{{ att.name }}</span>
              </div>
              <!-- 上传中的等待效果 -->
              <div v-if="att.uploading" class="attach-loading">
                <span class="spinner"></span>
              </div>
              <button
                v-else
                class="attach-del"
                title="移除"
                @click="removeAttachment(i)"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="10"
                  height="10"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
          <textarea
            ref="inputBox"
            v-model="userInput"
            rows="1"
            :placeholder="voiceRecording ? (voiceHint || '正在聆听…') : '输入你的问题'"
            @keydown.enter.exact.prevent="handleSend"
            @input="autoResize"
            @paste="onPaste"
          ></textarea>
          <div class="composer-bar">
            <div class="chips">
              <div v-if="modelCaps.image || modelCaps.doc" class="attach-wrap">
                <button
                  :class="['chip', 'plus-btn', { open: attachMenuOpen }]"
                  title="附件"
                  @click="attachMenuOpen = !attachMenuOpen"
                >
                  <svg
                    viewBox="0 0 24 24"
                    width="16"
                    height="16"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                  >
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                </button>
                <ul v-if="attachMenuOpen" class="attach-menu">
                  <li
                    v-if="modelCaps.doc"
                    class="attach-menu-item"
                    @click="pickFile('doc')"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      width="16"
                      height="16"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                      />
                      <path d="M14 2v6h6M9 15h6M9 11h2" />
                    </svg>
                    上传文档
                  </li>
                  <li
                    v-if="modelCaps.image"
                    class="attach-menu-item"
                    @click="pickFile('image')"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      width="16"
                      height="16"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <circle cx="9" cy="9" r="2" />
                      <path d="m21 15-4.5-4.5L6 21" />
                    </svg>
                    上传图片
                  </li>
                </ul>
              </div>
              <!-- 思考模式:仅当前模型支持时显示,点击开启/关闭 -->
              <button
                v-if="modelCaps.thinking"
                :class="['chip', { active: thinkingEnabled }]"
                :title="thinkingEnabled ? '关闭思考模式' : '开启思考模式'"
                @click="toggleThinking"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M12 2a7 7 0 0 1 7 7c0 2.4-1.2 4.2-2.6 5.6-.9.9-1.4 2.1-1.4 3.4H9c0-1.3-.5-2.5-1.4-3.4C6.2 13.2 5 11.4 5 9a7 7 0 0 1 7-7z"
                  />
                  <path d="M9 21h6" />
                </svg>
                思考
              </button>
              <!-- Agent 模式:开启后服务端 Agent 可自主调用工具(天气/计算/文档检索) -->
              <button
                :class="['chip', { active: agentEnabled }]"
                :title="agentEnabled ? '关闭 Agent 模式' : '开启 Agent 模式'"
                @click="toggleAgent"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="4" y="8" width="16" height="12" rx="2" />
                  <path d="M12 8V4M8 4h8" />
                  <circle cx="9" cy="13" r="1" />
                  <circle cx="15" cy="13" r="1" />
                  <path d="M9 17h6" />
                </svg>
                Agent
              </button>
              <button class="chip">
                <svg
                  viewBox="0 0 24 24"
                  width="15"
                  height="15"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
                研究
              </button>
            </div>
            <div class="composer-actions">
              <button
                :class="['icon-btn', 'mic-btn', { active: voiceRecording }]"
                :title="voiceRecording ? '停止语音输入' : '语音输入'"
                @click="toggleVoice"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                >
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                </svg>
              </button>
              <!-- 等待回答时:发送按钮变为终止按钮,点击中断当前请求 -->
              <button
                v-if="isLoading"
                class="send-btn stop"
                title="终止回答"
                @click="stopAgent"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="currentColor"
                >
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
              <button
                v-else
                class="send-btn"
                :disabled="
                  (!userInput.trim() && attachments.length === 0) ||
                  hasUploading
                "
                title="发送"
                @click="handleSend"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        <p class="disclaimer">内容由AI生成,可能不准确,请注意核实</p>
      </div>
    </main>

    <!-- 图片放大预览 -->
    <div v-if="previewImage" class="lightbox" @click="previewImage = null">
      <img :src="previewImage" alt="预览" />
    </div>

    <!-- 对话条数超限提示弹窗:全屏遮罩 + 居中对话框 -->
    <div
      v-if="limitDialogOpen"
      class="dialog-overlay"
      @click.self="limitDialogOpen = false"
    >
      <div class="dialog">
        <div class="dialog-header">
          <span class="dialog-title">提示</span>
          <button
            class="dialog-close"
            title="关闭"
            @click="limitDialogOpen = false"
          >
            <svg
              viewBox="0 0 24 24"
              width="16"
              height="16"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="dialog-body">对话已超过50条,请新建对话</div>
        <div class="dialog-footer">
          <button class="dialog-btn" @click="limitDialogOpen = false">
            取 消
          </button>
          <button class="dialog-btn primary" @click="confirmNewChat">
            确 定
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" src="./index.ts"></script>

<style scoped>
.layout {
  display: flex;
  height: 100svh;
  font-size: 14px;
  color: #1f2329;
  background: #fff;
}

/* ===== 左侧边栏 ===== */
.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #f9f9fa;
  border-right: 1px solid #f0f0f2;
  overflow: hidden;
}

/* 侧栏滑入滑出动画 */
.sidebar-slide-enter-active,
.sidebar-slide-leave-active {
  transition:
    width 0.25s ease,
    transform 0.25s ease,
    opacity 0.2s ease;
}
.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  width: 0;
  transform: translateX(-40px);
  opacity: 0;
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 12px;
}

.brand-name {
  font-size: 17px;
  font-weight: 700;
  color: #1f2329;
  white-space: nowrap;
}

.brand-actions {
  display: flex;
  gap: 2px;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #646a73;
  cursor: pointer;
}
.icon-btn:hover {
  background: #ececef;
}

/* 语音输入录音中:红色脉冲提示 */
.mic-btn.active {
  background: #fde2e2;
  color: #d9363e;
  animation: mic-pulse 1.2s ease-in-out infinite;
}
@keyframes mic-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(217, 54, 62, 0.35);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(217, 54, 62, 0);
  }
}

.new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 9px 0;
  margin-bottom: 8px;
  border: 1px solid #e5e5e8;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.new-chat:hover {
  background: #f2f2f4;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 16px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}
.menu-item:hover {
  background: #ececef;
}

/* 模型来源弹出菜单 */
.menu-item-wrap {
  position: relative;
}

.menu-item-wrap .menu-item {
  width: 100%;
}

.provider-tag {
  margin-left: auto;
  font-size: 12px;
  color: #8a8f99;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 模型来源浮层:fixed 定位悬浮在最上层,背景与侧栏一致 */
.attach-menu.provider-menu {
  position: fixed;
  bottom: auto;
  min-width: 140px;
  background: #f9f9fa;
}

.provider-menu .attach-menu-item {
  justify-content: space-between;
}

.provider-menu .attach-menu-item.active {
  color: #0a7aff;
}

.section-label {
  padding: 0 10px 6px;
  font-size: 12px;
  color: #8a8f99;
}

.conv-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: #1f2329;
}
.conv-item:hover {
  background: #ececef;
}
.conv-item.active {
  background: #e7e7ea;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.conv-del {
  display: none;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8a8f99;
  cursor: pointer;
  flex-shrink: 0;
}
.conv-item:hover .conv-del {
  display: inline-flex;
}
.conv-del:hover {
  background: #dddde1;
  color: #1f2329;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f0f0f2;
  position: relative;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.username {
  flex: 1;
  min-width: 0; /* 允许收缩,超长时显示省略号 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #1f2329;
}

/* 用户区域(头像 + 用户名):可点击,弹出用户菜单 */
.user-profile {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  margin: -4px -6px;
  border-radius: 8px;
  cursor: pointer;
}
.user-profile:hover {
  background: #f2f2f4;
}

/* 用户菜单弹窗:显示在用户区域上方,样式与模型下拉一致 */
.user-popup {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  width: 200px;
  padding: 6px;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 30;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
}
.user-item svg {
  color: #8a8f99;
  flex-shrink: 0;
}
.user-item:hover {
  background: #f2f2f4;
}
.user-item:hover svg {
  color: #1f2329;
}

/* 感叹号按钮:固定在最右侧 */
.info-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #b6b9c0;
  cursor: pointer;
}
.info-btn:hover {
  background: #f2f2f4;
  color: #1f2329;
}

/* 弹窗:v-if 控制显隐,显示在感叹号上方 */
.info-popup {
  position: absolute;
  bottom: calc(100% + 10px);
  right: 0;
  width: 230px;
  padding: 6px;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 30;
}

/* 菜单项样式与模型选择下拉一致 */
.info-item {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
}
.info-item:hover {
  background: #f2f2f4;
}

.info-footer {
  margin-top: 6px;
  padding: 10px 10px 4px;
  border-top: 1px solid #f0f0f2;
  font-size: 12px;
  line-height: 1.8;
  color: #8a8f99;
}

/* ===== 右侧主区域 ===== */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
  position: relative;
}

/* 消息区滚动条样式 */
.messages::-webkit-scrollbar {
  width: 6px;
}
.messages::-webkit-scrollbar-track {
  background: transparent;
}
.messages::-webkit-scrollbar-thumb {
  background: #e0e0e3;
  border-radius: 3px;
}
.messages::-webkit-scrollbar-thumb:hover {
  background: #c8cacd;
}

/* 右侧消息导航条 */
.msg-nav {
  position: absolute;
  right: 4px;
  top: 48px;
  bottom: 120px;
  width: 14px;
  z-index: 15;
}

.nav-dash {
  position: absolute;
  right: 0;
  width: 10px;
  height: 2px;
  border-radius: 1px;
  background: #d9dade;
  transform: translateY(-50%);
}
.msg-nav:hover .nav-dash {
  background: #b6b9c0;
}

.nav-panel {
  position: absolute;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  width: 260px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 6px;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.nav-item {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #8f939c;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}
.nav-item:hover {
  background: #f2f2f4;
}
/* 当前阅读位置对应的提问高亮为蓝色 */
.nav-item.active {
  color: #0a7aff;
  font-weight: 500;
}

.main-header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
}

.model-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  font-size: 16px;
  font-weight: 600;
  color: #1f2329;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}
.model-switch:hover {
  background: #f2f2f4;
}

.model-select {
  position: relative;
}

.model-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 20;
  min-width: 240px;
  max-height: 320px;
  overflow-y: auto;
  margin: 6px 0 0;
  padding: 6px;
  list-style: none;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
}
.model-option:hover {
  background: #f2f2f4;
}
.model-option.active {
  color: #0a7aff;
}
.model-option.empty {
  color: #8a8f99;
  cursor: default;
}
.model-option.empty:hover {
  background: transparent;
}

/* 模型搜索框:吸顶在弹层最上方,滚动列表时保持可见 */
.model-search {
  position: sticky;
  top: -6px; /* 抵消弹层 padding,吸到最顶 */
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -6px -6px 4px;
  padding: 10px 12px 8px;
  background: #fff;
  border-bottom: 1px solid #f0f0f2;
  color: #8a8f99;
  cursor: default;
}
.model-search input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 13px;
  color: #1f2329;
  background: transparent;
}
.model-search input::placeholder {
  color: #b6b9c0;
}

.model-name {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.dropdown-overlay {
  position: fixed;
  inset: 0;
  z-index: 10;
}

.messages {
  flex: 1;
  overflow-y: auto;
  /* 兜底:任何情况都不允许消息区出现全局横向滚动 */
  overflow-x: hidden;
  padding: 8px 24px;
}

/* 空对话欢迎语:logo + 问候,位于输入框正上方 */
.welcome {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 28px;
}

.welcome-logo {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
}

.welcome-text {
  font-size: 22px;
  font-weight: 600;
  color: #1f2329;
}

.msg-row {
  max-width: 768px;
  margin: 0 auto 16px;
  display: flex;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.msg-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 100%;
  /* flex 子项默认 min-width:auto,不设 0 时长内容会撑破容器产生横向滚动 */
  min-width: 0;
}

.msg-row.user .msg-col {
  align-items: flex-end;
  max-width: 100%;
  min-width: 0;
}

.msg-actions {
  display: flex;
  gap: 2px;
  margin-top: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.msg-row:hover .msg-actions {
  opacity: 1;
}

.msg-row.user .msg-actions {
  justify-content: flex-end;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8a8f99;
  cursor: pointer;
}
.action-btn:hover {
  background: #f2f2f4;
  color: #1f2329;
}

/* 禁用态(回答生成中):置灰且不可点击 */
.action-btn:disabled,
.action-btn:disabled:hover {
  background: transparent;
  color: #d4d6dc;
  cursor: not-allowed;
}

.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  /* 气泡不超出消息列;长 URL / 无空格字符串强制断行 */
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-wrap: anywhere;
}

.msg-row.user .bubble {
  background: #f2f2f4;
  max-width: 100%;
  box-sizing: border-box;
  border-top-right-radius: 4px;
}

.msg-row.assistant .bubble {
  background: transparent;
  padding-left: 0;
  padding-right: 0;
}

/* ===== Markdown 渲染内容(v-html 生成的标签需用 :deep 命中) ===== */
/* 渲染出的 HTML 自带块级结构,不再保留 pre-wrap 换行 */
.bubble:has(.markdown-body) {
  white-space: normal;
}

:deep(.markdown-body) {
  line-height: 1.7;
  font-size: 14px;
  color: #1f2329;
  /* 内容不撑破气泡:长串强制断行,宽块(代码/表格)内部横向滚动 */
  max-width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
}
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3),
:deep(.markdown-body h4) {
  margin: 14px 0 8px;
  line-height: 1.4;
}
:deep(.markdown-body h1) {
  font-size: 20px;
}
:deep(.markdown-body h2) {
  font-size: 18px;
}
:deep(.markdown-body h3) {
  font-size: 16px;
}
从 :deep(.markdown-body h4) {
  font-size: 15px;
}
:deep(.markdown-body p) {
  margin: 8px 0;
}
:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin: 8px 0;
  padding-left: 22px;
}
:deep(.markdown-body li) {
  margin: 4px 0;
}
:deep(.markdown-body a) {
  color: #0a7aff;
  text-decoration: none;
}
:deep(.markdown-body a:hover) {
  text-decoration: underline;
}
:deep(.markdown-body code) {
  /* 全局 style.css 里 code 是 inline-flex,行内代码改回 inline,长代码才能随文换行 */
  display: inline;
  background: #f2f2f4;
  border-radius: 4px;
  padding: 2px 5px;
  font-size: 13px;
  font-family: Consolas, Monaco, monospace;
}
:deep(.markdown-body pre) {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 10px 0;
}
:deep(.markdown-body pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

/* ===== 代码块(参考图样式:头部语言栏 + 复制 + 行号 + 浅色高亮) ===== */
:deep(.code-block) {
  margin: 10px 0;
  border: 1px solid #ececf0;
  border-radius: 10px;
  overflow: hidden;
  background: #f7f8fa;
  max-width: 100%;
}
:deep(.code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f0f0f3;
  border-bottom: 1px solid #ececf0;
}
:deep(.code-lang) {
  font-size: 12px;
  color: #6b7280;
  font-family: Consolas, Monaco, monospace;
}
:deep(.code-copy-btn) {
  border: none;
  background: transparent;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
:deep(.code-copy-btn:hover) {
  background: #e5e5e8;
  color: #1f2329;
}
:deep(.code-body) {
  margin: 0;
  padding: 10px 0;
  overflow-x: auto;
  background: transparent;
  counter-reset: codeline;
  font-size: 13px;
  line-height: 1.6;
}
:deep(.code-body code) {
  /* 全局 style.css 里 code 是 inline-flex,会把每行代码横排成 flex 项,必须改回 block */
  display: block;
  background: transparent;
  padding: 0;
  font-family: Consolas, Monaco, monospace;
}
/* 每行一个块,CSS 计数器生成行号 */
:deep(.code-line) {
  display: block;
  position: relative;
  padding-left: 46px;
  padding-right: 14px;
  counter-increment: codeline;
  min-height: 1.6em;
  white-space: pre;
}
:deep(.code-line)::before {
  content: counter(codeline);
  position: absolute;
  left: 14px;
  color: #b6b9c0;
  user-select: none;
}
:deep(.code-line:hover) {
  background: rgba(0, 0, 0, 0.03);
}
:deep(.markdown-body blockquote) {
  margin: 10px 0;
  padding: 4px 12px;
  border-left: 3px solid #d9dade;
  color: #6b7280;
}
:deep(.markdown-body table) {
  border-collapse: collapse;
  margin: 10px 0;
  width: 100%;
  /* 宽表格不撑破容器,表格自身出现横向滚动条 */
  display: block;
  overflow-x: auto;
}
:deep(.markdown-body th),
:deep(.markdown-body td) {
  border: 1px solid #e5e5e8;
  padding: 6px 10px;
  text-align: left;
}
:deep(.markdown-body th) {
  background: #f7f7f9;
}
:deep(.markdown-body img) {
  max-width: 100%;
  border-radius: 8px;
  cursor: zoom-in;
}
:deep(.markdown-body hr) {
  border: none;
  border-top: 1px solid #e5e5e8;
  margin: 14px 0;
}

/* 错误提示消息 */
.msg-row.assistant .bubble.error-bubble {
  background: #fff2f0;
  color: #cf1322;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  word-break: break-all;
}

/* 打字中动画 */
.typing {
  display: inline-flex;
  gap: 4px;
  padding: 4px 2px;
}
.typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #b6b9c0;
  animation: blink 1.2s infinite;
}
.typing i:nth-child(2) {
  animation-delay: 0.2s;
}
.typing i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%,
  60%,
  100% {
    opacity: 0.3;
  }
  30% {
    opacity: 1;
  }
}

/* 工具调用提示:工具调用期间显示,工具结果返回后自动消失 */
.tool-steps {
  margin: 4px 0;
  border-radius: 8px;
  background: #f7f8fa;
  border: 1px solid #ececf1;
  font-size: 13px;
  color: #6b7280;
  max-width: 560px;
}
.tool-steps summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  color: #9ca3af;
}
.tool-wrench {
  font-size: 12px;
}
.tool-steps-body {
  padding: 0 12px 8px;
  max-height: 240px;
  overflow-y: auto;
}
.tool-step {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 3px 0;
  line-height: 1.5;
}
.tool-step-icon {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  font-size: 12px;
}
.tool-step-icon.is-done {
  color: #16a34a;
}
.tool-step-icon.is-paused {
  color: #b7791f;
}
.tool-step-name {
  font-family: Consolas, Monaco, monospace;
  color: #0a7aff;
  font-weight: 500;
}
.tool-step-args {
  color: #9ca3af;
  font-size: 12px;
  word-break: break-all;
}
.tool-step-result {
  flex-basis: 100%;
  margin-left: 22px;
  color: #9ca3af;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.reasoning {
  margin: 4px 0;
  border-radius: 8px;
  background: #f7f8fa;
  border: 1px solid #ececf1;
  font-size: 13px;
  color: #6b7280;
}
.reasoning summary {
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 6px;
}
.reasoning-hint {
  color: #0a7aff;
  animation: reasoning-pulse 1.6s ease-in-out infinite;
}
@keyframes reasoning-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
.reasoning-body {
  padding: 0 12px 8px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
  line-height: 1.6;
}
.asset-card {
  margin-top: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafbfc;
  padding: 10px 12px;
  font-size: 13px;
  max-width: 560px;
}
.ac-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.ac-title {
  font-weight: 600;
  font-size: 14px;
}
.ac-steps {
  color: #9ca3af;
  font-size: 12px;
  white-space: nowrap;
}
.ac-group {
  margin-bottom: 4px;
}
.ac-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  cursor: pointer;
  border-bottom: 1px dashed #e5e7eb;
  margin-bottom: 2px;
}
.ac-group-head.readonly {
  cursor: default;
}
.asset-card-row.readonly {
  cursor: default;
}
.asset-card-row.readonly:hover {
  background: transparent;
}
.ac-group-name {
  font-weight: 600;
  color: #374151;
}
.ac-group-count {
  color: #9ca3af;
  font-size: 12px;
}
.ac-hint {
  flex: 1;
  align-self: center;
  color: #6b7280;
  font-size: 12px;
}
.ac-detail {
  cursor: default;
}
.ac-attr {
  padding: 1px 8px;
  border-radius: 999px;
  background: #f0f4ff;
  color: #4a5568;
  font-size: 12px;
  white-space: nowrap;
}
.ac-detail-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.asset-card-title {
  color: #6b7280;
  margin-bottom: 8px;
}
.asset-card-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 6px;
}
.asset-card-row.checked {
  background: #eef4ff;
}
.asset-card-label {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  cursor: pointer;
  min-width: 0;
}
.ac-name {
  font-weight: 500;
}
.ac-spec {
  color: #9ca3af;
  font-size: 12px;
}
.ac-stock {
  color: #0a7aff;
  font-size: 12px;
  white-space: nowrap;
}
.ac-exp {
  color: #9ca3af;
  font-size: 12px;
  white-space: nowrap;
}
.ac-qty {
  width: 72px;
  padding: 4px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
}
.asset-card-foot {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.ac-purpose {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 13px;
}
.ac-confirm {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: #0a7aff;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.ac-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ac-cancel {
  padding: 6px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}
.approval-card {
  margin-top: 8px;
  border: 1px solid #f5d08a;
  border-radius: 10px;
  background: #fffaf0;
  padding: 10px 12px;
  font-size: 13px;
  max-width: 560px;
}
.approval-title {
  color: #b7791f;
  font-weight: 500;
  margin-bottom: 8px;
}
.approval-list {
  margin: 0 0 10px;
  padding-left: 18px;
  line-height: 1.9;
}
.ap-action {
  display: inline-block;
  padding: 1px 8px;
  margin-right: 6px;
  border-radius: 6px;
  background: #f5d08a;
  color: #744210;
  font-size: 12px;
  font-weight: 500;
}
.approval-actions {
  display: flex;
  gap: 8px;
}
.ap-approve {
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  background: #0a7aff;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.ap-reject {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  color: #d93026;
  cursor: pointer;
  font-size: 13px;
}
.approval-form {
  margin-top: 8px;
  padding: 10px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.form-label {
  width: 72px;
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}
.form-select {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}
.form-textarea {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
}
.asset-panel {
  width: 100%;
  max-width: 720px;
  margin-bottom: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.ap-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.ap-tab {
  padding: 5px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}
.ap-tab.active {
  background: #0a7aff;
  border-color: #0a7aff;
  color: #fff;
}
.ap-body {
  max-height: 220px;
  overflow-y: auto;
  margin-bottom: 10px;
}
.ap-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ap-empty {
  color: #9ca3af;
  text-align: center;
  padding: 16px 0;
}
.ap-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
}
.ap-row:hover {
  background: #f5f7fa;
}
.ap-label {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  cursor: pointer;
  min-width: 0;
}
.ap-name {
  font-weight: 500;
}
.ap-spec {
  color: #9ca3af;
  font-size: 12px;
}
.ap-stock {
  color: #0a7aff;
  font-size: 12px;
  white-space: nowrap;
}
.ap-qty {
  width: 72px;
  padding: 4px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
}
.ap-select {
  flex: 1;
  min-width: 140px;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
}
.ap-arrow {
  color: #6b7280;
  font-weight: 500;
}
.ap-foot {
  display: flex;
  gap: 8px;
}
.ap-note {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 13px;
}
.ap-submit {
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  background: #0a7aff;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.ap-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ap-close {
  padding: 6px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}
/* 旋转图标(类似 loading 旋转) */
.tool-spin {
  color: #0a7aff;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ===== 底部输入区 ===== */
.composer-wrap {
  padding: 8px 24px 12px;
}

/* 空对话时:欢迎语 + 输入框作为整体垂直居中,发送首条消息后恢复底部布局 */
.composer-wrap.centered {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  padding: 0 24px;
}
.composer-wrap.centered .disclaimer {
  display: none;
}

.composer {
  max-width: 768px;
  margin: 0 auto;
  border: 1px solid #e5e5e8;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 12px 12px 8px;
}

.composer.disabled {
  opacity: 0.8;
}

.composer textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 1.5;
  font-family: inherit;
  color: #1f2329;
  background: transparent;
  max-height: 160px;
  box-sizing: border-box;
}

.composer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.chips {
  display: flex;
  gap: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  font-size: 13px;
  color: #646a73;
  cursor: pointer;
}
.chip:hover {
  background: #f2f2f4;
}

/* 思考模式开启态:背景灰(同悬浮效果)+ 字体蓝色 */
.chip.active,
.chip.active:hover {
  background: #f2f2f4;
  color: #0a7aff;
}

/* 「+」按钮:菜单展开时旋转 90° */
.plus-btn {
  transition: transform 0.2s ease;
}
.plus-btn.open {
  transform: rotate(90deg);
}

/* 附件弹出菜单 */
.attach-wrap {
  position: relative;
}

.attach-menu {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 20;
  min-width: 150px;
  margin: 0;
  padding: 6px;
  list-style: none;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.attach-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  color: #1f2329;
  white-space: nowrap;
  cursor: pointer;
}
.attach-menu-item:hover {
  background: #f2f2f4;
}

/* 输入框内的附件预览 */
.attach-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.attach-item {
  position: relative;
}

.attach-thumb {
  display: block;
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #e5e5e8;
}

.attach-file {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 200px;
  height: 56px;
  padding: 0 12px;
  border: 1px solid #e5e5e8;
  border-radius: 10px;
  font-size: 13px;
  color: #1f2329;
  box-sizing: border-box;
}

.attach-name {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.attach-del {
  position: absolute;
  top: -6px;
  right: -6px;
  display: none;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 50%;
  background: #1f2329;
  color: #fff;
  cursor: pointer;
  padding: 0;
}
.attach-item:hover .attach-del {
  display: inline-flex;
}

/* 上传中的等待效果 */
.attach-thumb.uploading {
  opacity: 0.6;
}

.attach-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.45);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #d0d3d9;
  border-top-color: #1f2329;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 图片放大预览 */
.msg-attach-thumb.clickable {
  cursor: zoom-in;
}

.lightbox {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  cursor: zoom-out;
}

.lightbox img {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

/* ===== 提示弹窗(全屏遮罩 + 居中对话框) ===== */
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}

.dialog {
  width: 380px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.16);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 0;
}

.dialog-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
}

.dialog-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8a8f99;
  cursor: pointer;
}
.dialog-close:hover {
  background: #f2f2f4;
  color: #1f2329;
}

.dialog-body {
  padding: 16px 18px 22px;
  font-size: 14px;
  line-height: 1.6;
  color: #4b4f58;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 0 18px 16px;
}

.dialog-btn {
  padding: 7px 18px;
  border: 1px solid #e5e5e8;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  color: #1f2329;
  cursor: pointer;
  transition: background 0.15s;
}
.dialog-btn:hover {
  background: #f2f2f4;
}
.dialog-btn.primary {
  border-color: #0a7aff;
  background: #0a7aff;
  color: #fff;
}
.dialog-btn.primary:hover {
  background: #0969dd;
}

/* 消息气泡内的附件展示 */
.msg-attach-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.msg-attach-thumb {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  display: block;
}

.msg-attach-file {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid #e5e5e8;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.send-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #1f2329;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.send-btn:disabled {
  background: #e5e5e8;
  color: #b6b9c0;
  cursor: not-allowed;
}

/* 终止按钮:悬浮时变红提示中断含义 */
.send-btn.stop:hover {
  background: #b3271e;
}

.disclaimer {
  max-width: 768px;
  margin: 6px auto 0;
  text-align: center;
  font-size: 12px;
  color: #b6b9c0;
}

/* ===== 登录/注册弹窗 ===== */
.auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(4px);
}

.auth-card {
  width: 380px;
  padding: 32px;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
}

.auth-header {
  text-align: center;
  margin-bottom: 24px;
}

.auth-logo {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  object-fit: cover;
  margin-bottom: 12px;
}

.auth-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2329;
}

.auth-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8a8f99;
}

.auth-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.auth-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.auth-field label {
  font-size: 13px;
  color: #646a73;
}

.auth-field input {
  padding: 10px 12px;
  border: 1px solid #e5e5e8;
  border-radius: 10px;
  font-size: 14px;
  color: #1f2329;
  outline: none;
  transition: border-color 0.15s;
}

.auth-field input:focus {
  border-color: #0a7aff;
}

.auth-error {
  margin: 0;
  font-size: 13px;
  color: #b3271e;
  text-align: center;
}

.auth-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px 0;
  border: none;
  border-radius: 10px;
  background: #1f2329;
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.auth-submit:hover {
  background: #33383f;
}

.auth-submit:disabled {
  background: #d4d6dc;
  cursor: not-allowed;
}

.auth-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
}

.auth-link {
  border: none;
  background: transparent;
  font-size: 13px;
  color: #0a7aff;
  cursor: pointer;
}

.auth-link:hover {
  text-decoration: underline;
}
</style>
