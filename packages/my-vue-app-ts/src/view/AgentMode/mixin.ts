// @ts-nocheck
/**
 * AgentMode 逻辑混入(composable):
 * 包含会话管理、模型/来源切换、附件上传、Agent 调用、消息导航等全部状态与方法,
 * 由 index.ts 的 setup() 混入返回给模板使用。
 * (原组件为 JS 写法,迁移时保留原语义,故关闭本文件的 TS 检查)
 */
import { ref, computed, watch, nextTick, onMounted } from "vue";
import MarkdownIt from "markdown-it";
// highlight.js 按需引入:只注册实际用到的语言,避免全量打包(压缩后省 ~900KB)
import hljs from "highlight.js/lib/core";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import json from "highlight.js/lib/languages/json";
import cssLang from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import python from "highlight.js/lib/languages/python";
import java from "highlight.js/lib/languages/java";
import bash from "highlight.js/lib/languages/bash";
import sql from "highlight.js/lib/languages/sql";
import "highlight.js/styles/vs.css"; // 浅色高亮主题(绿色注释,贴近参考图)

hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("css", cssLang);
hljs.registerLanguage("xml", xml); // html/svg/vue 等走 xml 规则
hljs.registerLanguage("html", xml);
hljs.registerLanguage("python", python);
hljs.registerLanguage("java", java);
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("sql", sql);
import beautify from "js-beautify";
import { get, post, put, patch, del } from "../../axios";
import { extractErrorMessage } from "../../axios/utils";
import { fetchSSE } from "../../axios/sse";
import { useVoiceInput } from "./voice";

// Markdown 渲染器:不放行原始 HTML(防 XSS),自动识别链接,换行转 <br>
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

/**
 * 展示前格式化代码,压掉超长单行(否则代码块横向滚动条过长)。
 * 支持 JS/TS/JSON/CSS/HTML 系,其余语言保持原样;格式化失败回退原文。
 */
const formatCode = (code, lang) => {
  try {
    if (lang === "json") return JSON.stringify(JSON.parse(code), null, 2);
    const opts = { indent_size: 2 };
    if (/^(javascript|js|typescript|ts|jsx|tsx)$/.test(lang))
      return beautify.js(code, opts);
    if (/^(css|scss|less)$/.test(lang)) return beautify.css(code, opts);
    if (/^(html|xml|vue|svg)$/.test(lang))
      return beautify.html(code, { ...opts, wrap_line_length: 80 });
  } catch {
    /* 无法解析时用原文展示 */
  }
  return code;
};

/**
 * 模型有时把换行输出为字面 "\n" 两个字符(转义产物),渲染时会显示成一行。
 * 当字面 \n 远多于真实换行时,判定为转义产物并还原为真实换行/制表/引号。
 */
const unescapeLiteralNewlines = (text) => {
  const literal = (text.match(/\\n/g) || []).length;
  const real = (text.match(/\n/g) || []).length;
  if (literal < 2 || literal <= real * 2) return text; // 正常内容不动
  return text
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"');
};

/**
 * 判断一段(不在代码块内的)文本是否其实是裸代码。
 * 模型有时会把代码作为普通文本返回(甚至整段一行),不包 ```。
 */
const looksLikeCode = (text) => {
  const signals = [
    /\/\*\*/, // JSDoc 开头
    /\bfunction\s+\w*\s*\(/, // 函数定义
    /\b(const|let|var)\s+\w+\s*=/, // 变量声明
    /=\>\s*\{?/, // 箭头函数
    /\b(for|while)\s*\(/, // 循环
    /\bif\s*\([^)]*\)\s*\{/, // 条件块
    /\bclass\s+\w+/, // 类定义
    /[;}\)]\s*$/m, // 以分号/大括号/右括号结尾的行
  ];
  let hits = 0;
  for (const re of signals) if (re.test(text)) hits++;
  return hits >= 3;
};

/**
 * 渲染前预处理:按 ``` 分段,裸代码段自动包进代码块,
 * 交给 fence 渲染(高亮 + 格式化)统一处理;普通文本不受影响。
 */
const normalizeCodeBlocks = (content) =>
  content
    .split(/(```[\s\S]*?(?:```|$))/g)
    .map((part) => {
      if (part.startsWith("```") || !looksLikeCode(part)) return part;
      return "\n```\n" + part.trim() + "\n```\n";
    })
    .join("");

/**
 * 把高亮后的 HTML 按行包上 .code-line(配合 CSS 计数器显示行号)。
 * 跨行的高亮 <span>(多行注释/字符串)在行尾临时闭合、下一行重新打开,保证 HTML 合法。
 */
const wrapCodeLines = (html) => {
  const openTags = [];
  return html
    .split("\n")
    .map((line) => {
      let out = openTags.join("") + line;
      const re = /<\/?span[^>]*>/g;
      let m;
      while ((m = re.exec(line)) !== null) {
        if (m[0].startsWith("</")) openTags.pop();
        else openTags.push(m[0]);
      }
      out += "</span>".repeat(openTags.length);
      return `<span class="code-line">${out}</span>`;
    })
    .join("");
};

// 自定义代码块渲染:头部(语言名 + 复制按钮) + 行号代码体,贴近参考图样式
md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx];
  // fence 内容末尾自带换行,去掉避免多出一个空行号
  const raw = token.content.replace(/\n+$/, "");
  let lang = (token.info || "").trim().split(/\s+/)[0].toLowerCase();
  // 无语言标记时在常见语言范围内自动识别(模型经常只写 ``` 不带语言),
  // 识别出可格式化的语言同样先格式化
  if (!lang || !hljs.getLanguage(lang)) {
    const auto = hljs.highlightAuto(raw, [
      "javascript",
      "typescript",
      "json",
      "css",
      "xml",
      "python",
      "java",
      "bash",
      "sql",
    ]);
    if (auto.language && auto.relevance >= 5) lang = auto.language;
  }
  const code = formatCode(raw, lang);
  let codeHtml;
  if (lang && hljs.getLanguage(lang)) {
    try {
      codeHtml = hljs.highlight(code, { language: lang }).value;
    } catch {
      codeHtml = md.utils.escapeHtml(code);
    }
  } else {
    codeHtml = md.utils.escapeHtml(code);
  }
  const langLabel = md.utils.escapeHtml(lang || "text");
  return (
    `<div class="code-block">` +
    `<div class="code-header"><span class="code-lang">${langLabel}</span>` +
    `<button type="button" class="code-copy-btn">复制</button></div>` +
    `<pre class="code-body hljs"><code>${wrapCodeLines(codeHtml)}</code></pre>` +
    `</div>`
  );
};

export function useAgentMixin(auth) {
  // (原步骤 2 之前: LangChain ChatOpenAI 与 get_weather 工具定义在前端)
  // (步骤 3 起: 模型与 Agent 编排已在 FastAPI 层完成,前端仅裸 fetch 收 SSE)

  // 1. 会话状态(经 NestJS 代理持久化到 ai-service/MySQL,按登录用户隔离)
  // local: true 表示本地草稿(尚未落库),首次发消息时才创建服务端会话,
  // 避免点击"新建对话"就产生空会话记录
  const createConv = () => ({
    id: crypto.randomUUID(),
    title: "新对话",
    messages: [],
    local: true,
    loaded: true,
  });

  const conversations = ref<any[]>([createConv()]);
  const activeId = ref(conversations.value[0].id);

  // 从服务端拉取会话列表(不含消息),并加载第一个会话的消息
  const loadConvsFromServer = async () => {
    try {
      const json = await get("/v1/conversations");
      const list = (json.conversations ?? []).map((c) => ({
        ...c,
        messages: [],
        local: false,
        loaded: false,
      }));
      if (list.length === 0) return; // 无历史会话:保留初始本地草稿
      conversations.value = list;
      activeId.value = list[0].id;
      await loadMessages(list[0].id);
    } catch (error) {
      console.error("加载会话列表失败", error);
    }
  };

  // 按需加载某个会话的消息(服务端列表接口不带消息)
  const loadMessages = async (id) => {
    const conv = conversations.value.find((c) => c.id === id);
    if (!conv || conv.local || conv.loaded) return;
    try {
      const json = await get(`/v1/conversations/${id}`);
      conv.messages = (json.messages ?? []).map((m) => ({
        role: m.role,
        content: m.content,
        attachments: m.attachments ?? [],
        ...(m.flags?.error ? { error: true } : {}),
        ...(m.flags?.aborted ? { aborted: true } : {}),
      }));
      conv.loaded = true;
    } catch (error) {
      console.error("加载会话消息失败", error);
    }
  };

  // 本地草稿首次发消息时落库;返回后 conv.id 变为服务端 id
  const ensureServerConv = async (conv) => {
    if (!conv.local) return;
    const created = await post("/v1/conversations", { title: conv.title });
    conv.id = created.id;
    conv.local = false;
    activeId.value = conv.id;
  };

  // 附件随聊天请求带给服务端(展示元数据;文档文本已由 toOpenAIMessage
  // 拼进 content,图片不入库,故 text/url 等大字段都不必再带)
  const serializeAttachments = (atts) =>
    (atts ?? []).map((a) => ({
      type: a.type,
      name: a.name,
      fileId: a.fileId,
    }));

  const userInput = ref("");
  const isLoading = ref(false);
  const msgBox = ref(null);
  const inputBox = ref(null);
  const sidebarCollapsed = ref(false);
  // 左下角「关于」弹窗:点击感叹号开启/关闭
  const infoOpen = ref(false);
  const toggleInfo = () => {
    infoOpen.value = !infoOpen.value;
  };
  // 用户菜单弹窗:点击用户区域开启/关闭
  const userMenuOpen = ref(false);
  const toggleUserMenu = () => {
    userMenuOpen.value = !userMenuOpen.value;
  };

  const activeConv = computed(
    () =>
      conversations.value.find((c) => c.id === activeId.value) ??
      conversations.value[0],
  );
  const activeMessages = computed<any[]>(
    () => activeConv.value?.messages ?? [],
  );

  // 模型列表与当前模型(由后端管理,切换后对后续所有请求生效)
  const models = ref<any[]>([]);
  const currentModel = ref("");
  const showDropdown = ref(false);
  // 当前模型能力:是否支持上传图片 / 文档 / 思考模式(由后端返回)
  const modelCaps = ref({ image: true, doc: true, thinking: false });
  // 思考模式开关(仅当前模型支持时可开启)
  const thinkingEnabled = ref(false);
  const toggleThinking = () => {
    thinkingEnabled.value = !thinkingEnabled.value;
  };

  // Agent 模式开关:默认开启。开启后请求带 use_agent,服务端 Agent 自主决定
  // 调工具还是直接回答;来源不支持 tool_calls 时服务端自动回落直答
  const agentEnabled = ref(true);
  const toggleAgent = () => {
    agentEnabled.value = !agentEnabled.value;
  };

  // 切换模型后来源能力变化:新模型不支持思考时自动关闭开关
  watch(
    () => modelCaps.value.thinking,
    (supported) => {
      if (!supported) thinkingEnabled.value = false;
    },
  );
  // 模型来源(公司模型 / 百炼模型等,由后端管理)
  const providers = ref<any[]>([]);
  const currentProvider = ref("");
  const providerMenuOpen = ref(false);
  const providerBtn = ref(null);
  const providerMenuStyle = ref({});

  // 浮层用 fixed 定位,悬浮在最上层且不受侧栏滚动容器裁剪
  const toggleProviderMenu = () => {
    if (!providerMenuOpen.value && providerBtn.value) {
      const r = providerBtn.value.getBoundingClientRect();
      providerMenuStyle.value = { top: `${r.top}px`, left: `${r.right + 8}px` };
    }
    providerMenuOpen.value = !providerMenuOpen.value;
  };

  const currentProviderName = computed(
    () =>
      providers.value.find((p) => p.key === currentProvider.value)?.name ?? "",
  );

  const loadModels = async () => {
    try {
      const json = await get("/v1/models");
      if (json.capabilities) modelCaps.value = json.capabilities;
      // 兼容 { data: [{id}] } 与 { data: ["k3"] } 两种返回格式
      const list = Array.isArray(json.data?.data) ? json.data.data : [];
      models.value = list.map((m) => (typeof m === "string" ? m : m.id));

      // 切换来源后:后端返回的 current 可能为空或不在新列表中,
      // 此时默认选中第一个可用模型,避免右侧模型固定写死或为空
      const returned = json.current ?? "";
      if (returned && models.value.includes(returned)) {
        currentModel.value = returned;
      } else if (models.value.length > 0) {
        currentModel.value = models.value[0];
      } else {
        currentModel.value = "";
      }
    } catch (error) {
      console.error("加载模型列表失败", error);
    }
  };

  onMounted(async () => {
    try {
      const json = await get("/v1/providers");
      providers.value = json.providers ?? [];
      currentProvider.value = json.current ?? "";
    } catch (error) {
      console.error("加载模型来源失败", error);
    }
    loadModels();
    await loadConvsFromServer(); // 从数据库拉回当前用户的历史会话
    scrollToBottom(true); // 刷新页面后定位到最新消息
  });

  // 切换模型来源:通知后端,然后重新查询新来源的模型列表
  const changeProvider = async (key) => {
    if (key === currentProvider.value) return;
    try {
      await put("/v1/providers/current", { provider: key });
      currentProvider.value = key;
      await loadModels();
    } catch (error) {
      console.error("切换模型来源失败", error);
    }
  };

  // 弹出菜单中点击来源:切换并收起菜单
  const selectProvider = (key) => {
    providerMenuOpen.value = false;
    changeProvider(key);
  };

  // 右侧消息导航:仅针对用户的提问生成短横线,悬浮显示提问预览,点击跳转
  const navItems = ref<any[]>([]);
  const navOpen = ref(false);
  // 当前阅读位置对应的提问(滚动消息区时更新,导航面板中高亮为蓝色)
  const navActiveIndex = ref(-1);

  const refreshNav = async () => {
    await nextTick();
    const box = msgBox.value;
    if (!box) return;
    const rows = box.querySelectorAll(".msg-row");
    const total = box.scrollHeight || 1;
    navItems.value = Array.from(rows)
      .map((el, i) => ({ el, msg: activeMessages.value[i] ?? {}, index: i }))
      .filter(({ msg }) => msg.role === "user")
      .map(({ el, msg, index }) => {
        const text = (msg.content || "")
          .replace(/!\[[^\]]*\]\([^)]*\)/g, "[图片]")
          .trim();
        return {
          index,
          top: Math.min((el.offsetTop / total) * 100, 99),
          offsetTop: el.offsetTop,
          preview: text ? text.slice(0, 24) : "[附件]",
          role: msg.role,
        };
      });
    updateNavActive();
  };

  // 滚动事件:更新导航当前项,同时记录用户是否贴底
  // (上滑查看历史时暂停流式自动滚动,回到底部恢复)
  const updateNavActive = () => {
    const box = msgBox.value;
    if (!box) return;
    stickToBottom.value =
      box.scrollHeight - box.scrollTop - box.clientHeight <= BOTTOM_THRESHOLD;
    if (navItems.value.length === 0) return;
    const readLine = box.scrollTop + 80;
    let active = navItems.value[0].index;
    for (const item of navItems.value) {
      if (item.offsetTop <= readLine) active = item.index;
      else break;
    }
    navActiveIndex.value = active;
  };

  const openNav = () => {
    refreshNav(); // 图片加载后高度可能变化,悬浮时重新计算位置
    navOpen.value = true;
  };

  const jumpTo = (index) => {
    const rows = msgBox.value?.querySelectorAll(".msg-row");
    rows?.[index]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  watch(activeMessages, refreshNav, { deep: true });

  const toggleDropdown = () => {
    showDropdown.value = !showDropdown.value;
    if (showDropdown.value) modelFilter.value = ""; // 每次打开重置搜索
  };

  // 模型搜索过滤(按名称包含匹配,不区分大小写)
  const modelFilter = ref("");
  const filteredModels = computed(() => {
    const kw = modelFilter.value.trim().toLowerCase();
    if (!kw) return models.value;
    return models.value.filter((m) => m.toLowerCase().includes(kw));
  });

  const selectModel = async (m) => {
    showDropdown.value = false;
    if (m === currentModel.value) return;
    try {
      const json = await put("/v1/models/current", { model: m });
      currentModel.value = json.current;
      if (json.capabilities) modelCaps.value = json.capabilities;
    } catch (error) {
      console.error("切换模型失败", error);
    }
  };

  // 是否贴着消息区底部(用户上滑查看历史时置 false,回到底部恢复 true)
  const stickToBottom = ref(true);
  const BOTTOM_THRESHOLD = 40; // 距底部多少像素内算"贴底"

  // 滚动到底部;force 用于发送消息/切换会话等必须到底的场景。
  // 流式输出期间用户上滑后 stickToBottom=false,不再强制跟随
  const scrollToBottom = async (force = false) => {
    if (!force && !stickToBottom.value) return;
    await nextTick();
    if (msgBox.value) {
      msgBox.value.scrollTop = msgBox.value.scrollHeight;
      stickToBottom.value = true;
    }
  };

  // 4. 侧栏操作
  const newChat = () => {
    const conv = createConv(); // 本地草稿,首条消息发出时才落库
    conversations.value.unshift(conv);
    activeId.value = conv.id;
    nextTick(() => inputBox.value?.focus());
  };

  const selectConv = async (id) => {
    if (isLoading.value) return;
    activeId.value = id;
    await loadMessages(id); // 服务端会话按需拉取消息
    scrollToBottom(true); // 切换会话强制定位到底部
  };

  const removeConv = async (id) => {
    const idx = conversations.value.findIndex((c) => c.id === id);
    if (idx === -1) return;
    const conv = conversations.value[idx];
    // 联动删除该会话已上传到后端的附件(失败不影响会话删除)
    const fileIds = conv.messages
      .flatMap((m) => m.attachments ?? [])
      .map((a) => a.fileId)
      .filter(Boolean);
    if (fileIds.length > 0) {
      post("/v1/files/delete", { ids: fileIds }).catch((error) =>
        console.error("删除附件失败", error),
      );
    }
    // 服务端会话同步删除(本地草稿无需请求)
    if (!conv.local) {
      del(`/v1/conversations/${id}`).catch((error) =>
        console.error("删除会话失败", error),
      );
    }
    conversations.value.splice(idx, 1);
    if (conversations.value.length === 0) {
      conversations.value.push(createConv());
    }
    if (activeId.value === id) {
      activeId.value = conversations.value[0].id;
      loadMessages(activeId.value);
    }
  };

  // 输入框自适应高度
  const autoResize = () => {
    const el = inputBox.value;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  // 语音输入:点击麦克风开启/关闭,识别文本实时追加到 userInput
  const { voiceRecording, voiceHint, toggleVoice, stopVoice } = useVoiceInput({
    userInput,
    autoResize,
  });

  // 附件上传(「+」菜单:上传文档 / 上传图片)
  const attachMenuOpen = ref(false);
  const attachments = ref<any[]>([]);
  const docInput = ref(null);
  const imgInput = ref(null);

  const pickFile = (kind) => {
    attachMenuOpen.value = false;
    (kind === "image" ? imgInput : docInput).value?.click();
  };

  // 上传文件到后端,返回 { id, name, kind, text? }
  const uploadFile = async (f) => {
    const fd = new FormData();
    fd.append("files", f);
    const [info] = await post("/v1/files/upload", fd);
    return info;
  };

  const readAsDataURL = (f) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(f);
    });

  // 添加附件:先插入带等待效果的占位项,上传完成后替换
  const addAttachment = async (f, kind) => {
    const placeholder = {
      type: kind === "image" ? "image" : "file",
      name: f.name || "粘贴的图片.png",
      url: kind === "image" ? URL.createObjectURL(f) : undefined,
      uploading: true,
    };
    attachments.value.push(placeholder);
    try {
      const info = await uploadFile(f);
      const finalAtt = {
        type: placeholder.type,
        name: info.name,
        fileId: info.id,
        text: info.text,
        url:
          kind === "image"
            ? await readAsDataURL(f) // base64,用于随消息发给模型
            : undefined,
      };
      const idx = attachments.value.indexOf(placeholder);
      if (idx !== -1) attachments.value.splice(idx, 1, finalAtt);
      if (kind === "image") URL.revokeObjectURL(placeholder.url);
    } catch (error) {
      console.error("上传失败", error);
      const idx = attachments.value.indexOf(placeholder);
      if (idx !== -1) attachments.value.splice(idx, 1);
      alert(`文件「${placeholder.name}」上传失败`);
    }
  };

  const onPick = (e, kind) => {
    const files = Array.from(e.target.files || []);
    e.target.value = ""; // 允许重复选择同一文件
    for (const f of files) addAttachment(f, kind);
  };

  // 输入框粘贴图片直接上传
  const onPaste = (e) => {
    if (!modelCaps.value.image) return; // 当前模型不支持图片
    const items = Array.from(e.clipboardData?.items || []);
    const imageItems = items.filter(
      (it) => it.kind === "file" && it.type.startsWith("image/"),
    );
    if (imageItems.length === 0) return;
    e.preventDefault();
    for (const it of imageItems) {
      const f = it.getAsFile();
      if (f) addAttachment(f, "image");
    }
  };

  // 是否有附件正在上传中(上传完成前禁止发送)
  const hasUploading = computed(() =>
    attachments.value.some((a) => a.uploading),
  );

  // 图片放大预览
  const previewImage = ref<any>(null);

  // 将助手回复拆分为文本 / 图片(Markdown 图片语法)片段,图片可点击放大
  const renderSegments = (content) => {
    const segs = [];
    const re = /!\[([^\]]*)\]\(([^)\s]+)\)/g;
    let last = 0;
    let m;
    while ((m = re.exec(content)) !== null) {
      if (m.index > last)
        segs.push({ type: "text", text: content.slice(last, m.index) });
      segs.push({ type: "image", url: m[2], alt: m[1] });
      last = re.lastIndex;
    }
    if (last < content.length)
      segs.push({ type: "text", text: content.slice(last) });
    return segs;
  };

  // Markdown 渲染:后端标识为 markdown 的助手回复用 markdown-it 转成 HTML;
  // 渲染前先把字面 \n 还原为真实换行,再把裸代码段包进代码块
  const renderMarkdown = (content) =>
    md.render(normalizeCodeBlocks(unescapeLiteralNewlines(content || "")));

  // 是否按 Markdown 渲染:优先用后端标识;流式响应没有标识(或历史消息),
  // 渲染时实时检测 markdown 语法 / 裸代码兜底
  const MD_PATTERN =
    /(^|\n)\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>\s)|```|(\|[^|\n]+\|){2,}|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\n]+\)/;
  const shouldRenderMarkdown = (msg) =>
    !!msg.markdown ||
    MD_PATTERN.test(String(msg.content ?? "")) ||
    looksLikeCode(String(msg.content ?? ""));

  // Markdown 内容内的点击委托(v-html 无法直接绑事件):
  // - 点击图片放大预览
  // - 点击代码块「复制」按钮复制代码原文
  const onMarkdownClick = async (e) => {
    const copyBtn = e.target?.closest?.(".code-copy-btn");
    if (copyBtn) {
      const code =
        copyBtn.closest(".code-block")?.querySelector("code")?.innerText ?? "";
      try {
        await navigator.clipboard.writeText(code);
        copyBtn.textContent = "已复制";
        setTimeout(() => {
          copyBtn.textContent = "复制";
        }, 1500);
      } catch {
        /* 剪贴板不可用时静默 */
      }
      return;
    }
    if (e.target?.tagName === "IMG") previewImage.value = e.target.src;
  };

  const removeAttachment = (index) => {
    attachments.value.splice(index, 1);
  };

  // 5. 消息操作:复制 / 重发 / 重新生成
  const copiedIndex = ref(-1);

  const copyMessage = async (msg, index) => {
    try {
      await navigator.clipboard.writeText(msg.content);
    } catch {
      // 剪贴板 API 不可用时的降级方案
      const ta = document.createElement("textarea");
      ta.value = msg.content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    copiedIndex.value = index;
    setTimeout(() => {
      if (copiedIndex.value === index) copiedIndex.value = -1;
    }, 1500);
  };

  // 6. 核心 Agent 交互逻辑(步骤 3:前端剥离 LangChain,裸 fetch 收 SSE)
  // - 历史消息转 OpenAI 格式:文档文本拼到用户消息,图片仅最后一条带 image_url
  const toOpenAIMessage = (m, isLast) => {
    const atts = m.attachments ?? [];
    let text = m.content;
    for (const a of atts) {
      if (a.type === "file" && a.text) text += `\n\n【附件文档:${a.name}】\n${a.text}`;
    }
    const images = isLast ? atts.filter((a) => a.type === "image" && a.url) : [];
    if (!isLast && atts.some((a) => a.type === "image")) {
      text += "\n\n(用户此前上传过图片)";
    }
    if (images.length === 0) return { role: m.role, content: text };
    return {
      role: m.role,
      content: [
        { type: "text", text },
        ...images.map((a) => ({ type: "image_url", image_url: { url: a.url } })),
      ],
    };
  };

  // 从后端错误响应里提取可读原因(NestJS/FastAPI 统一 { error: { message } } 格式)
  const extractErrorMessage = (error) => {
    let text = error?.message || String(error);
    for (let i = 0; i < 3; i++) {
      const match = text.match(/\{[\s\S]*\}/);
      if (!match) break;
      try {
        const j = JSON.parse(match[0]);
        const next = j?.error?.message ?? j?.message;
        if (typeof next !== "string" || next === text) break;
        text = next;
      } catch { break; }
    }
    return text;
  };

  // 走 FastAPI 的 SSE 流(自定义事件流):token/tool_start/tool_end/done/error
  let abortController: AbortController | null = null;

  // 通用 SSE 消费:把一轮流式输出写进 assistantMsg。
  // runAgent(新提问)与 submitApproval(HITL 审批恢复)共用。
  const streamChat = async (conv, assistantMsg, body) => {
    isLoading.value = true;
    abortController = new AbortController();
    const { signal } = abortController;

    const RENDER_INTERVAL = 120;
    let lastRender = 0;
    let flushTimer = null;
    const flush = () => {
      if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
      assistantMsg.loading = false;
      scrollToBottom();
      lastRender = Date.now();
    };
    const scheduleFlush = () => {
      const elapsed = Date.now() - lastRender;
      if (elapsed >= RENDER_INTERVAL) flush();
      else if (!flushTimer) flushTimer = setTimeout(flush, RENDER_INTERVAL - elapsed);
    };

    try {
      await fetchSSE({
        url: "/api/v1/chat/completions",
        body,
        signal,
        onEvent: ({ event, data }) => {
          switch (event) {
            case "token":
              // 正文开始 = 思考结束:自动收起思考面板(用户仍可手动展开)
              assistantMsg.reasoningStreaming = false;
              if (assistantMsg.reasoningOpen !== undefined) {
                assistantMsg.reasoningOpen = false;
              }
              assistantMsg.content += data.content || "";
              scheduleFlush();
              break;
            case "reasoning":
              // 3.3 思考过程流式透传:与正文分开累积;
              // 思考 token 一出现就默认展开面板,思考结束由 token 分支收起。
              // reasoningStreaming 驱动面板标题的「深度思考中…」动态提示,
              // 让用户明确正文需等思考全部生成完才会出现(模型固有顺序)。
              assistantMsg.reasoningStreaming = true;
              if (assistantMsg.reasoningOpen === undefined) {
                assistantMsg.reasoningOpen = true;
              }
              assistantMsg.reasoning = (assistantMsg.reasoning || "") + (data.content || "");
              scheduleFlush();
              break;
            case "approval_request":
              // HITL:图在写操作工具内 interrupt 暂停,渲染审批卡片;
              // 进行中的工具步骤标记为"已暂停"(不再转圈),等待用户决策
              (assistantMsg.toolSteps || []).forEach((s) => {
                if (s.status === "running") s.status = "paused";
              });
              assistantMsg.approval = { items: data.items || [] };
              scheduleFlush();
              break;
            case "tool_start":
              // 工具调用步骤:主流展示为可折叠的步骤列表,进行中自动展开
              if (!assistantMsg.toolSteps) assistantMsg.toolSteps = [];
              assistantMsg.toolSteps.push({
                name: data.name || "tool",
                args: data.args || {},
                status: "running",
                result: "",
              });
              assistantMsg.toolStepsOpen = true;
              scheduleFlush();
              break;
            case "tool_end": {
              // 收尾最后一个进行中的步骤(优先同名);全部完成时自动收起
              const steps = assistantMsg.toolSteps || [];
              let target = [...steps].reverse().find(
                (s) => s.status === "running" && s.name === data.name,
              ) || [...steps].reverse().find((s) => s.status === "running");
              if (target) {
                target.status = "done";
                target.result = String(data.result ?? "").slice(0, 300);
              }
              if (!steps.some((s) => s.status === "running")) {
                assistantMsg.toolStepsOpen = false;
              }
              scheduleFlush();
              break;
            }
            case "done":
              break;
          }
        },
      });
      flush();
    } catch (error) {
      if (signal.aborted) {
        assistantMsg.aborted = true;
        if (!assistantMsg.content) assistantMsg.content = "已终止回答";
      } else {
        console.error(error);
        assistantMsg.content = `请求失败:${extractErrorMessage(error)}`;
        assistantMsg.error = true;
      }
    } finally {
      // 兜底关闭:任何结束路径(完成/出错/终止)都不允许工具步骤一直转圈
      const steps = assistantMsg.toolSteps || [];
      steps.forEach((s) => {
        if (s.status === "running") s.status = "done";
      });
      if (!steps.some((s) => s.status === "running")) {
        assistantMsg.toolStepsOpen = false;
      }
      assistantMsg.loading = false;
      assistantMsg.reasoningStreaming = false;
      isLoading.value = false;
      abortController = null;
      scrollToBottom();
      // 助手消息(含出错/终止标志)由服务端在流收尾时统一落库
    }
  };

  const runAgent = async (conv, extra = {}) => {
    conv.messages.push({ role: "assistant", content: "", loading: true });
    const assistantMsg = conv.messages[conv.messages.length - 1];
    scrollToBottom(true);

    const rawMessages = conv.messages.slice(0, -1);
    const lastUserMsg = [...rawMessages].reverse().find((m) => m.role === "user");
    // 会话持久化所有权收敛:Agent 模式的推理上下文由服务端 checkpoint 提供,
    // 只发本轮新消息(用户/助手消息都由服务端落库);
    // 直答模式无 checkpoint,仍发全量历史;regenerate 时 Agent 模式发空 + keep 标记
    const useAgent = agentEnabled.value;
    const fullHistory = () =>
      rawMessages.map((m, i) => toOpenAIMessage(m, i === rawMessages.length - 1));
    const messages = useAgent
      ? extra.regenerate
        ? []
        : lastUserMsg
          ? [toOpenAIMessage(lastUserMsg, true)]
          : []
      : fullHistory();

    await streamChat(conv, assistantMsg, {
      model: currentModel.value,
      messages,
      stream: true,
      // 思考模式始终显式传布尔值:不传时上游思考型模型(qwen3/deepseek/k3)
      // 默认开思考,必须显式 false 才会关闭;联网搜索仍由后端来源默认处理
      enable_thinking: thinkingEnabled.value,
      ...(useAgent ? { use_agent: true } : {}),
      // HITL:会话 id 作为 LangGraph thread_id,审批断点按它定位
      conversation_id: conv.id,
      // 展示元数据:服务端落库本轮用户消息用(文档文本已在 content 内)
      ...(lastUserMsg && !extra.regenerate
        ? { attachments: serializeAttachments(lastUserMsg.attachments) }
        : {}),
      ...extra,
    });
  };

  // HITL 审批:把批准/拒绝决策发回后端,图从 interrupt 断点恢复执行,
  // 恢复后的输出流进一条新的 assistant 消息
  const submitApproval = async (msg, decision: "approve" | "reject") => {
    if (isLoading.value) return;
    const conv = activeConv.value;
    msg.approval = null; // 审批卡片一次性
    conv.messages.push({ role: "assistant", content: "", loading: true });
    const assistantMsg = conv.messages[conv.messages.length - 1];
    scrollToBottom(true);
    await streamChat(conv, assistantMsg, {
      model: currentModel.value,
      messages: [], // resume 路径不读 messages
      stream: true,
      use_agent: true,
      conversation_id: conv.id,
      resume: { decision },
    });
  };

  // HITL 交互式审批:审批卡片里的职级选择与理由填写状态
  // key 用 msg.approval.items[0].id(interrupt id),value 存 {jobLevelId, reason}
  const approvalSelections = ref(new Map());

  // 提交带选项的审批(职级调整):把用户选择的职级 id 和理由一起塞进 resume
  const submitApprovalWithOptions = async (msg, item, decision: "approve" | "reject") => {
    if (isLoading.value) return;
    const conv = activeConv.value;
    msg.approval = null;
    conv.messages.push({ role: "assistant", content: "", loading: true });
    const assistantMsg = conv.messages[conv.messages.length - 1];
    scrollToBottom(true);

    const sel = approvalSelections.value.get(item.id) || {};
    const resume: Record<string, unknown> = { decision };
    if (decision === "approve") {
      resume.jobLevelId = sel.jobLevelId || null;
      resume.reason = sel.reason || "";
    }
    // 提交后清理本地选择状态,避免内存泄漏
    approvalSelections.value.delete(item.id);

    await streamChat(conv, assistantMsg, {
      model: currentModel.value,
      messages: [],
      stream: true,
      use_agent: true,
      conversation_id: conv.id,
      resume,
    });
  };

  // 终止当前正在进行的回答;终止后 isLoading 复位,可再次发送
  const stopAgent = () => {
    abortController?.abort();
  };

  // 单个对话的消息条数上限(用户 + 助手合计)
  const MAX_MESSAGES = 50;
  // 条数超限提示弹窗
  const limitDialogOpen = ref(false);

  // 达到条数上限:弹出提示,确认后新建对话
  const checkMessageLimit = (conv) => {
    if (conv.messages.length < MAX_MESSAGES) return false;
    limitDialogOpen.value = true;
    return true;
  };

  // 弹窗「确定」:关闭弹窗并切换到新对话;已有空白新对话时直接跳转,不再重复创建
  const confirmNewChat = () => {
    limitDialogOpen.value = false;
    // 只看已加载的会话:未加载的服务端会话 messages 为空,不能误判为空白对话
    const empty = conversations.value.find(
      (c) => c.loaded && c.messages.length === 0,
    );
    if (empty) {
      activeId.value = empty.id;
      nextTick(() => inputBox.value?.focus());
    } else {
      newChat();
    }
  };

  const handleSend = async () => {
    const text = userInput.value.trim();
    if (
      (!text && attachments.value.length === 0) ||
      isLoading.value ||
      hasUploading.value
    )
      return;

    stopVoice(); // 发送前先停录音,避免识别结果追加到已清空的输入框

    const conv = activeConv.value;
    if (checkMessageLimit(conv)) return; // 达到上限,当前消息不发送
    const atts = attachments.value.map((a) => ({ ...a }));
    attachments.value = [];
    userInput.value = "";
    // 等 Vue 把空值渲染到 textarea 后再重算高度,否则拿到的还是旧内容的 scrollHeight
    nextTick(() => autoResize());

    // 记录用户消息;首条消息作为会话标题
    const content = text || "请查看我上传的附件";
    const userMsg = { role: "user", content, attachments: atts };
    conv.messages.push(userMsg);
    const isFirstMessage = conv.messages.length === 1;
    if (conv.title === "新对话") conv.title = content.slice(0, 20);

    try {
      // 本地草稿先落库为服务端会话(conversation_id 是聊天请求的必备字段);
      // 用户消息由服务端在聊天流程中落库,前端不再逐条追加
      await ensureServerConv(conv);
      if (isFirstMessage) {
        patch(`/v1/conversations/${conv.id}`, { title: conv.title }).catch(
          (error) => console.error("更新会话标题失败", error),
        );
      }
    } catch (error) {
      console.error("会话落库失败,本次消息仅保存在本地", error);
    }
    runAgent(conv);
  };

  // 重发:把该用户消息内容作为新消息再次发送
  const resendMessage = async (msg) => {
    if (isLoading.value) return;
    const conv = activeConv.value;
    if (checkMessageLimit(conv)) return;
    const userMsg = { role: "user", content: msg.content };
    conv.messages.push(userMsg);
    try {
      await ensureServerConv(conv);
    } catch (error) {
      console.error("会话落库失败", error);
    }
    runAgent(conv);
  };

  // 工具步骤块(模板用,避免模板内联箭头函数):
  const toolStepsRunning = (msg): boolean =>
    (msg.toolSteps || []).some((s) => s.status === "running");

  // 步骤块 summary 文案:"调用工具 2 个 · 进行中/等待审批/已完成"
  const toolStepSummary = (msg): string => {
    const steps = msg.toolSteps || [];
    const state = steps.some((s) => s.status === "running")
      ? "进行中"
      : steps.some((s) => s.status === "paused")
        ? "等待审批"
        : "已完成";
    return `调用工具 ${steps.length} 个 · ${state}`;
  };

  // 单步参数摘要(截断,完整参数不必上屏)
  const toolArgsSummary = (step): string => {
    const s = JSON.stringify(step.args || {});
    return s.length > 60 ? s.slice(0, 60) + "…" : s;
  };

  // 重新生成:删除该助手回复及其后的所有消息,基于之前的上下文重新请求。
  // Agent 模式:keep 告诉服务端截断展示轨道到该位置,并从对应 checkpoint
  // 分叉重跑(真正回到该时点);直答模式:重发截断后的全量历史
  const regenerate = (index) => {
    if (isLoading.value) return;
    const conv = activeConv.value;
    conv.messages.splice(index);
    runAgent(conv, { regenerate: { keep: index } });
  };

  // 混入到组件 setup 的全部状态与方法
  return {
    // 会话与布局
    conversations,
    activeId,
    sidebarCollapsed,
    infoOpen,
    toggleInfo,
    userMenuOpen,
    toggleUserMenu,
    newChat,
    selectConv,
    removeConv,
    // 模型与来源
    models,
    currentModel,
    showDropdown,
    toggleDropdown,
    selectModel,
    modelFilter,
    filteredModels,
    modelCaps,
    thinkingEnabled,
    toggleThinking,
    agentEnabled,
    toggleAgent,
    providers,
    currentProvider,
    currentProviderName,
    providerMenuOpen,
    providerBtn,
    providerMenuStyle,
    toggleProviderMenu,
    selectProvider,
    // 消息区
    activeMessages,
    msgBox,
    previewImage,
    renderSegments,
    renderMarkdown,
    shouldRenderMarkdown,
    onMarkdownClick,
    copiedIndex,
    copyMessage,
    regenerate,
    resendMessage,
    toolStepsRunning,
    toolStepSummary,
    toolArgsSummary,
    submitApproval,
    submitApprovalWithOptions,
    approvalSelections,
    navItems,
    navOpen,
    navActiveIndex,
    updateNavActive,
    openNav,
    jumpTo,
    // 输入与附件
    userInput,
    isLoading,
    inputBox,
    handleSend,
    stopAgent,
    autoResize,
    onPaste,
    voiceRecording,
    voiceHint,
    toggleVoice,
    attachMenuOpen,
    pickFile,
    attachments,
    removeAttachment,
    docInput,
    imgInput,
    onPick,
    hasUploading,
    // 条数上限弹窗
    limitDialogOpen,
    confirmNewChat,
  };
}
