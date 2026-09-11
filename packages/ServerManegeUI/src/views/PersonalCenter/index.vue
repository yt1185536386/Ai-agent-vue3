<template>
  <div>
    <!-- 顶部:标题 -->
    <div class="head-row">
      <div>
        <h2 class="page-title">个人中心</h2>
        <div class="page-subtitle profile-sub-en">PROFILE&nbsp;·&nbsp;ACCOUNT</div>
      </div>
    </div>

    <!-- 账号资料卡 -->
    <div class="page-card profile-card">
      <div class="profile-top">
        <div class="avatar-wrap">
          <el-avatar :size="64" class="avatar">{{ avatarText }}</el-avatar>
          <span class="online-dot" />
        </div>
        <div class="profile-meta">
          <div class="profile-name">
            {{ me?.username }}
            <el-tag size="small" effect="plain" type="primary" round>
              <el-icon size="12"><CircleCheck /></el-icon>
              {{ permissionText }}
            </el-tag>
          </div>
          <div class="profile-contact">
            <span class="contact-item">
              <el-icon><Message /></el-icon>{{ me?.email || '未设置邮箱' }}
            </span>
            <span class="contact-item">
              <el-icon><Link /></el-icon>未设置电话
            </span>
          </div>
        </div>
      </div>

      <div class="profile-fields">
        <div class="field">
          <div class="field-label">用户名</div>
          <div class="field-value">{{ me?.username }}</div>
        </div>
        <div class="field">
          <div class="field-label">角色</div>
          <div class="field-value">{{ permissionText }}</div>
        </div>
        <div class="field">
          <div class="field-label">所属部门</div>
          <div class="field-value">{{ me?.department?.name || '未分配' }}</div>
        </div>
        <div class="field">
          <div class="field-label">邮箱</div>
          <div class="field-value">{{ me?.email || '—' }}</div>
        </div>
        <div class="field">
          <div class="field-label">电话</div>
          <div class="field-value">—</div>
        </div>
      </div>
    </div>

    <!-- 账号设置 -->
    <div class="page-card settings-card">
      <div class="settings-head">
        <el-icon><Setting /></el-icon>
        <span>账号设置</span>
      </div>

      <div class="setting-row">
        <div class="setting-icon"><el-icon><User /></el-icon></div>
        <div class="setting-text">
          <div class="setting-title">账号信息</div>
          <div class="setting-desc">维护邮箱、电话等基础资料</div>
        </div>
        <el-button text type="primary" @click="infoDialog = true">
          <el-icon><Edit /></el-icon>修改
        </el-button>
      </div>

      <div class="setting-row">
        <div class="setting-icon"><el-icon><Lock /></el-icon></div>
        <div class="setting-text">
          <div class="setting-title">账号安全</div>
          <div class="setting-desc">定期更换密码可提升账号安全性</div>
        </div>
        <el-button text type="primary" @click="pwdDialog = true">
          <el-icon><Unlock /></el-icon>修改密码
        </el-button>
      </div>

      <div class="setting-row">
        <div class="setting-icon"><el-icon><Key /></el-icon></div>
        <div class="setting-text">
          <div class="setting-title">API 令牌</div>
          <div class="setting-desc">查看与管理已签发的 API 访问令牌</div>
        </div>
        <el-button text type="primary" @click="tokenDialog = true">
          管理<el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 修改账号信息 -->
    <el-dialog v-model="infoDialog" title="修改账号信息" width="440px">
      <el-alert type="info" :closable="false" show-icon class="dialog-tip"
        title="资料保存接口暂未开放,当前仅支持查看" />
      <el-form label-width="72px" class="dialog-form">
        <el-form-item label="用户名">
          <el-input :model-value="me?.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="infoForm.email" placeholder="请输入邮箱" disabled />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="infoForm.phone" placeholder="请输入电话" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="infoDialog = false">关 闭</el-button>
        <el-button type="primary" disabled>保 存</el-button>
      </template>
    </el-dialog>

    <!-- 修改密码 -->
    <el-dialog v-model="pwdDialog" title="修改密码" width="440px">
      <el-alert type="info" :closable="false" show-icon class="dialog-tip"
        title="修改密码接口暂未开放,当前仅支持查看" />
      <el-form label-width="72px" class="dialog-form">
        <el-form-item label="原密码">
          <el-input type="password" show-password placeholder="请输入原密码" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input type="password" show-password placeholder="请输入新密码" disabled />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input type="password" show-password placeholder="请再次输入新密码" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialog = false">关 闭</el-button>
        <el-button type="primary" disabled>确 定</el-button>
      </template>
    </el-dialog>

    <!-- API 令牌 -->
    <el-dialog v-model="tokenDialog" title="API 令牌" width="520px">
      <el-empty description="暂无已签发的 API 令牌" :image-size="90" />
      <template #footer>
        <el-button @click="tokenDialog = false">关 闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const me = computed(() => auth.user)

const infoDialog = ref(false)
const pwdDialog = ref(false)
const tokenDialog = ref(false)
const infoForm = reactive({ email: me.value?.email || '', phone: '' })

const avatarText = computed(() => (me.value?.username || 'U').slice(0, 1).toUpperCase())
const DEPT_POSITION_TEXT: Record<string, string> = {
  MANAGER: '经理', DEPUTY: '副经理', LEADER: '组长', MEMBER: '组员',
}
const permissionText = computed(() => {
  if (me.value?.isSuperAdmin) return '超级管理员'
  const pos = me.value?.deptPosition ? DEPT_POSITION_TEXT[me.value.deptPosition] : null
  return pos || '普通用户'
})
</script>

<style scoped>
.head-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.profile-sub-en { letter-spacing: 2px; }

.profile-card { padding: 0; overflow: hidden; margin-bottom: 14px; }
.profile-top { display: flex; align-items: center; gap: 18px; padding: 24px 24px 20px; }
.avatar-wrap { position: relative; flex-shrink: 0; }
.avatar { background: #e8f0fe; color: #2563eb; font-size: 26px; font-weight: 600; border: 2px solid #d6e4ff; }
.online-dot {
  position: absolute; right: 2px; bottom: 2px;
  width: 12px; height: 12px; border-radius: 50%;
  background: #22c55e; border: 2px solid #fff;
}
.profile-name { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 600; color: #1f2d3d; }
.profile-name .el-tag { display: inline-flex; align-items: center; gap: 3px; }
.profile-contact { display: flex; gap: 18px; margin-top: 8px; font-size: 13px; color: #909399; }
.contact-item { display: inline-flex; align-items: center; gap: 5px; }

.profile-fields {
  display: grid; grid-template-columns: repeat(5, 1fr);
  border-top: 1px solid #f2f3f5; padding: 14px 24px 18px;
}
.field-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.field-value { font-size: 14px; color: #1f2d3d; }

.settings-card { padding: 6px 20px; }
.settings-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 15px; font-weight: 600; color: #1f2d3d;
  padding: 14px 4px; border-bottom: 1px solid #f2f3f5;
}
.setting-row {
  display: flex; align-items: center; gap: 14px;
  padding: 16px 4px; border-bottom: 1px solid #f7f8fa;
}
.setting-row:last-child { border-bottom: none; }
.setting-icon {
  width: 36px; height: 36px; border-radius: 8px;
  background: #f4f6fa; color: #606266;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; flex-shrink: 0;
}
.setting-text { flex: 1; min-width: 0; }
.setting-title { font-size: 14px; font-weight: 600; color: #1f2d3d; }
.setting-desc { font-size: 12px; color: #909399; margin-top: 2px; }
.setting-row .el-button { display: inline-flex; align-items: center; gap: 4px; }

.dialog-tip { margin-bottom: 14px; }
.dialog-form { margin-top: 4px; }

@media (max-width: 900px) {
  .profile-fields { grid-template-columns: repeat(2, 1fr); row-gap: 14px; }
}
</style>
