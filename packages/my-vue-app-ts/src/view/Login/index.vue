<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthMixin } from "../AgentMode/auth-mixin";

const router = useRouter();
const auth = useAuthMixin();

const handleLoginSuccess = () => {
  // submitAuth 内部捕获错误不抛出,需根据登录态判断是否跳转
  if (auth.isLoggedIn.value) {
    router.replace("/");
  }
};
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-header">
        <img
          class="auth-logo"
          src="../../assets/Ericicon/icon1.png"
          alt="logo"
        />
        <h3>{{ auth.isRegister.value ? '注册账号' : '欢迎回来' }}</h3>
        <p class="auth-subtitle">Eric agent 智能助手</p>
      </div>
      <div class="auth-body">
        <div class="auth-field">
          <label>用户名</label>
          <input
            v-model="auth.authForm.value.username"
            type="text"
            placeholder="请输入用户名"
            @keydown.enter="auth.submitAuth().then(handleLoginSuccess)"
          />
        </div>
        <div class="auth-field">
          <label>密码</label>
          <input
            v-model="auth.authForm.value.password"
            type="password"
            placeholder="请输入密码"
            @keydown.enter="auth.submitAuth().then(handleLoginSuccess)"
          />
        </div>
        <p v-if="auth.authError.value" class="auth-error">{{ auth.authError.value }}</p>
        <button
          class="auth-submit"
          :disabled="auth.isAuthLoading.value"
          @click="auth.submitAuth().then(handleLoginSuccess)"
        >
          <span v-if="auth.isAuthLoading.value" class="auth-spinner"></span>
          <span>{{ auth.isRegister.value ? '注册' : '登录' }}</span>
        </button>
      </div>
      <div class="auth-footer">
        <button class="auth-link" @click="auth.isRegister.value = !auth.isRegister.value">
          {{ auth.isRegister.value ? '已有账号? 去登录' : '没有账号? 去注册' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f7f8fa;
}

.auth-card {
  width: 380px;
  padding: 32px;
  background: #fff;
  border: 1px solid #e5e5e8;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.06);
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
