<template>
  <div class="login-page">
    <!-- 背景装饰 -->
    <div class="bg-decor" aria-hidden="true">
      <div class="grid-lines"></div>
      <div class="glow glow-a"></div>
      <div class="glow glow-b"></div>
    </div>

    <!-- 顶部品牌 -->
    <header class="page-header">
      <div class="logo-mark">
        <svg viewBox="0 0 40 40" width="40" height="40">
          <defs>
            <linearGradient id="lg-logo" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#4f8cff" />
              <stop offset="1" stop-color="#1d4ed8" />
            </linearGradient>
          </defs>
          <path
            d="M20 2 36 11v18L20 38 4 29V11L20 2z"
            fill="none"
            stroke="url(#lg-logo)"
            stroke-width="2.5"
          />
          <path
            d="M20 10 29 15v10l-9 5-9-5V15l9-5z"
            fill="url(#lg-logo)"
            opacity="0.9"
          />
          <path d="M20 15 25 18v5l-5 2.8L15 23v-5l5-3z" fill="#fff" />
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-title">模型服务网关</div>
        <div class="brand-sub">MODEL SERVICE GATEWAY</div>
      </div>
    </header>

    <main class="page-main">
      <!-- 左侧展示区 -->
      <section class="hero">
        <h1 class="hero-title">模型服务网关</h1>
        <p class="hero-slogan">统一接入 ｜ 安全管控 ｜ 高效调用</p>
        <div class="hero-tags">
          <span class="tag">
            <el-icon :size="15"><Box /></el-icon>多模型接入
          </span>
          <span class="tag">
            <el-icon :size="15"><Lock /></el-icon>全链路管控
          </span>
          <span class="tag">
            <el-icon :size="15"><Monitor /></el-icon>实时监控
          </span>
        </div>

        <!-- 网关插画 -->
        <div class="hero-illustration" aria-hidden="true">
          <svg viewBox="0 0 520 380" class="illu">
            <defs>
              <linearGradient id="ig-platform" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#dbeafe" />
                <stop offset="1" stop-color="#93c5fd" />
              </linearGradient>
              <linearGradient id="ig-frame" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#eff6ff" />
                <stop offset="1" stop-color="#bfdbfe" />
              </linearGradient>
              <linearGradient id="ig-core" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#60a5fa" />
                <stop offset="1" stop-color="#2563eb" />
              </linearGradient>
              <linearGradient id="ig-cube" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#e0f2fe" />
                <stop offset="1" stop-color="#7dd3fc" />
              </linearGradient>
              <filter id="ig-glow" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="8" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <!-- 地面光晕 -->
            <ellipse cx="260" cy="330" rx="220" ry="34" fill="#bfdbfe" opacity="0.35" />
            <ellipse cx="260" cy="330" rx="140" ry="20" fill="#93c5fd" opacity="0.3" />

            <!-- 底座平台 -->
            <g>
              <path d="M90 300 260 240 430 300 260 360Z" fill="url(#ig-platform)" />
              <path d="M90 300 90 316 260 376 260 360Z" fill="#93c5fd" />
              <path d="M430 300 430 316 260 376 260 360Z" fill="#60a5fa" />
              <path d="M140 292 260 250 380 292 260 336Z" fill="#eff6ff" opacity="0.7" />
            </g>

            <!-- 基座立柱 -->
            <g>
              <path d="M170 300 170 252 186 244 186 292Z" fill="#bfdbfe" />
              <path d="M350 292 350 244 366 252 366 300Z" fill="#93c5fd" />
            </g>

            <!-- 中央六边形门框 -->
            <g filter="url(#ig-glow)">
              <path
                d="M260 92 336 136v88l-76 44-76-44v-88l76-44z"
                fill="url(#ig-frame)"
                stroke="#93c5fd"
                stroke-width="2"
              />
              <path
                d="M260 112 318 146v68l-58 34-58-34v-68l58-34z"
                fill="#dbeafe"
              />
              <!-- 门内光柱 -->
              <path d="M236 150 236 214 260 228 260 164Z" fill="#93c5fd" opacity="0.6" />
              <path d="M284 150 284 214 260 228 260 164Z" fill="#60a5fa" opacity="0.5" />
              <!-- 核心六边形 -->
              <path
                class="core-hex"
                d="M260 158 288 174v32l-28 16-28-16v-32l28-16z"
                fill="url(#ig-core)"
              />
              <path d="M260 170 276 179v18l-8 4.6V184l-8-4.6-8 4.6v17.4l-8-4.6v-18l16-9z" fill="#fff" opacity="0.9" />
            </g>

            <!-- 顶部标牌 -->
            <g>
              <path d="M216 78 304 78 318 96 202 96Z" fill="#e0f2fe" stroke="#7dd3fc" />
              <text x="260" y="91" text-anchor="middle" font-size="12" font-weight="700" fill="#1d4ed8" letter-spacing="2">MSGW</text>
            </g>

            <!-- 浮岛方块 -->
            <g class="float-cube" style="animation-delay: 0s">
              <path d="M96 196 128 180 160 196 128 212Z" fill="#e0f2fe" />
              <path d="M96 196 96 218 128 234 128 212Z" fill="#7dd3fc" />
              <path d="M160 196 160 218 128 234 128 212Z" fill="#38bdf8" />
              <text x="128" y="212" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">API</text>
            </g>
            <g class="float-cube" style="animation-delay: 0.6s">
              <path d="M376 176 404 162 432 176 404 190Z" fill="#e0f2fe" />
              <path d="M376 176 376 196 404 210 404 190Z" fill="#7dd3fc" />
              <path d="M432 176 432 196 404 210 404 190Z" fill="#38bdf8" />
              <text x="404" y="192" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">RAG</text>
            </g>
            <g class="float-cube" style="animation-delay: 1.2s">
              <path d="M64 268 96 252 128 268 96 284Z" fill="#f0f9ff" />
              <path d="M64 268 64 290 96 306 96 284Z" fill="#bae6fd" />
              <path d="M128 268 128 290 96 306 96 284Z" fill="#7dd3fc" />
              <text x="96" y="284" text-anchor="middle" font-size="10" font-weight="700" fill="#0284c7">LLM</text>
            </g>
            <g class="float-cube" style="animation-delay: 1.8s">
              <path d="M392 276 420 262 448 276 420 290Z" fill="#f0f9ff" />
              <path d="M392 276 392 296 420 310 420 290Z" fill="#bae6fd" />
              <path d="M448 276 448 296 420 310 420 290Z" fill="#7dd3fc" />
              <text x="420" y="292" text-anchor="middle" font-size="9" font-weight="700" fill="#0284c7">TOOLS</text>
            </g>

            <!-- 连接线 -->
            <g stroke="#7dd3fc" stroke-width="1.4" stroke-dasharray="4 5" opacity="0.8" fill="none">
              <path d="M128 212 190 250" />
              <path d="M404 210 336 244" />
              <path d="M96 252 160 262" />
              <path d="M420 262 366 262" />
            </g>
          </svg>
        </div>
      </section>

      <!-- 右侧登录卡片 -->
      <section class="login-card">
        <h2 class="card-title">欢迎登录</h2>
        <p class="card-sub">开启安全、稳定的模型服务体验</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          label-position="top"
          @keyup.enter="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              :prefix-icon="Lock"
            />
          </el-form-item>
          <el-form-item label="验证码" prop="captcha">
            <div class="captcha-row">
              <el-input
                v-model="form.captcha"
                placeholder="请输入验证码"
                :prefix-icon="Key"
                class="captcha-input"
              />
              <canvas
                ref="captchaRef"
                class="captcha-canvas"
                width="112"
                height="40"
                title="点击刷新验证码"
                @click="drawCaptcha"
              ></canvas>
            </div>
          </el-form-item>

          <div class="form-extra">
            <el-checkbox v-model="form.remember">记住我</el-checkbox>
            <el-link type="primary" :underline="false" @click="onForgot">
              忘记密码？
            </el-link>
          </div>

          <el-button
            type="primary"
            class="submit"
            :loading="loading"
            @click="submit"
            >登 录</el-button
          >

          <p class="agreement">
            登录即表示您已阅读并同意
            <el-link type="primary" :underline="false">《服务协议》</el-link>
            和
            <el-link type="primary" :underline="false">《隐私政策》</el-link>
          </p>
        </el-form>
      </section>
    </main>

    <!-- 页脚 -->
    <footer class="page-footer">
      <span>© 2026 模型服务网关 All Rights Reserved.</span>
      <div class="footer-links">
        <el-link :underline="false">技术支持</el-link>
        <el-link :underline="false">使用帮助</el-link>
        <el-link :underline="false">隐私政策</el-link>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { User, Lock, Key, Box, Monitor } from "@element-plus/icons-vue";
import { authApi } from "@/api";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const REMEMBER_KEY = "msgw_remember_username";

const formRef = ref<FormInstance>();
const form = reactive({
  username: localStorage.getItem(REMEMBER_KEY) || "",
  password: "",
  captcha: "",
  remember: !!localStorage.getItem(REMEMBER_KEY),
});

const captchaRef = ref<HTMLCanvasElement>();
let captchaText = "";

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
  captcha: [
    { required: true, message: "请输入验证码", trigger: "blur" },
    {
      validator: (_r, v: string, cb) =>
        !v || v.toLowerCase() === captchaText.toLowerCase()
          ? cb()
          : cb(new Error("验证码不正确")),
      trigger: "blur",
    },
  ],
};
const loading = ref(false);

/** 绘制本地图形验证码（前端校验，后端如需可替换为接口返回的图片） */
function drawCaptcha() {
  const canvas = captchaRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  captchaText = Array.from(
    { length: 4 },
    () => chars[Math.floor(Math.random() * chars.length)]
  ).join("");

  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#f4f8ff";
  ctx.fillRect(0, 0, width, height);

  // 干扰线
  for (let i = 0; i < 4; i++) {
    ctx.strokeStyle = `hsl(${Math.random() * 360},60%,70%)`;
    ctx.beginPath();
    ctx.moveTo(Math.random() * width, Math.random() * height);
    ctx.lineTo(Math.random() * width, Math.random() * height);
    ctx.stroke();
  }
  // 字符
  const palette = ["#2563eb", "#0ea5e9", "#7c3aed", "#0891b2"];
  captchaText.split("").forEach((ch, i) => {
    ctx.save();
    ctx.font = `italic 700 ${22 + Math.random() * 4}px serif`;
    ctx.fillStyle = palette[i % palette.length];
    ctx.translate(16 + i * 24, height / 2 + 6);
    ctx.rotate((Math.random() - 0.5) * 0.5);
    ctx.fillText(ch, -8, 0);
    ctx.restore();
  });
  // 干扰点
  for (let i = 0; i < 24; i++) {
    ctx.fillStyle = `hsl(${Math.random() * 360},50%,60%)`;
    ctx.fillRect(Math.random() * width, Math.random() * height, 1.6, 1.6);
  }
}

onMounted(drawCaptcha);

function onForgot() {
  ElMessage.info("请联系系统管理员重置密码");
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    drawCaptcha();
    form.captcha = "";
    return;
  }
  loading.value = true;
  try {
    const { data } = await authApi.login(form.username, form.password);
    // NestJS 登录响应为原生 { access_token, user } 结构
    auth.setSession(data.access_token, data.user);
    // 登录后立即拉取有效权限码(菜单显隐依赖)
    await auth.loadPerms();
    if (form.remember) localStorage.setItem(REMEMBER_KEY, form.username);
    else localStorage.removeItem(REMEMBER_KEY);
    ElMessage.success("登录成功");
    router.push((route.query.redirect as string) || "/dashboard");
  } catch {
    drawCaptcha();
    form.captcha = "";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(160deg, #eef4ff 0%, #f7faff 45%, #ffffff 100%);
}

/* 背景装饰 */
.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(147, 197, 253, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(147, 197, 253, 0.12) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 70% at 30% 40%, #000 30%, transparent 75%);
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
}
.glow-a {
  width: 480px;
  height: 480px;
  left: -120px;
  top: -80px;
  background: rgba(147, 197, 253, 0.35);
}
.glow-b {
  width: 420px;
  height: 420px;
  right: -100px;
  bottom: -120px;
  background: rgba(191, 219, 254, 0.4);
}

/* 顶部品牌 */
.page-header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 28px 48px 0;
}
.brand-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
  line-height: 1.2;
}
.brand-sub {
  font-size: 10px;
  color: #94a3b8;
  letter-spacing: 2px;
}

/* 主区域 */
.page-main {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 48px;
  padding: 24px 96px;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

/* 左侧展示 */
.hero {
  flex: 1;
  min-width: 0;
}
.hero-title {
  font-size: 42px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 12px;
  letter-spacing: 2px;
}
.hero-slogan {
  font-size: 17px;
  color: #475569;
  margin: 0 0 22px;
  letter-spacing: 1px;
}
.hero-tags {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  font-size: 13px;
  color: #1e40af;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(147, 197, 253, 0.5);
  border-radius: 999px;
  box-shadow: 0 2px 10px rgba(59, 130, 246, 0.08);
  backdrop-filter: blur(4px);
}
.hero-illustration {
  margin-top: 8px;
  max-width: 520px;
}
.illu {
  width: 100%;
  height: auto;
}
.core-hex {
  animation: core-pulse 3s ease-in-out infinite;
  transform-origin: 260px 190px;
}
@keyframes core-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.75; }
}
.float-cube {
  animation: float-y 4s ease-in-out infinite;
}
@keyframes float-y {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* 右侧登录卡片 */
.login-card {
  width: 420px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 16px;
  padding: 40px 44px 28px;
  box-shadow:
    0 24px 60px rgba(37, 99, 235, 0.12),
    0 2px 8px rgba(37, 99, 235, 0.06);
  backdrop-filter: blur(8px);
}
.card-title {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 6px;
}
.card-sub {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 24px;
}
.captcha-row {
  display: flex;
  gap: 12px;
  width: 100%;
}
.captcha-input {
  flex: 1;
}
.captcha-canvas {
  width: 112px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid #dcdfe6;
  cursor: pointer;
  flex-shrink: 0;
}
.form-extra {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 16px;
}
.submit {
  width: 100%;
  font-size: 16px;
  letter-spacing: 6px;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  border: none;
}
.submit:hover {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
}
.agreement {
  margin: 18px 0 0;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}
.agreement .el-link {
  font-size: 12px;
  vertical-align: baseline;
}

/* 页脚 */
.page-footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 48px;
  font-size: 12px;
  color: #94a3b8;
}
.footer-links {
  display: flex;
  gap: 24px;
}
.footer-links .el-link {
  font-size: 12px;
  color: #94a3b8;
}

/* 响应式：窄屏隐藏左侧插画 */
@media (max-width: 1100px) {
  .hero-illustration {
    display: none;
  }
}
@media (max-width: 900px) {
  .page-main {
    justify-content: center;
    padding: 24px 24px;
  }
  .hero {
    display: none;
  }
  .page-header {
    padding: 20px 24px 0;
  }
  .page-footer {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
