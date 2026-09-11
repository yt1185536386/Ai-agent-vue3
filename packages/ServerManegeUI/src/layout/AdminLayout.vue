<template>
  <el-container class="admin-layout">
    <el-aside :width="collapsed ? '64px' : '216px'" class="sidebar">
      <div class="logo" @click="$router.push('/dashboard')">
        <div class="logo-icon">
          <el-icon :size="22" color="#fff"><Connection /></el-icon>
        </div>
        <div v-if="!collapsed" class="logo-text">
          <div class="logo-title">模型服务网关</div>
          <div class="logo-sub">MODEL SERVICE GATEWAY</div>
        </div>
      </div>

      <el-menu
        :default-active="$route.path"
        :collapse="collapsed"
        router
        class="menu"
      >
        <div v-if="!collapsed" class="menu-group">总览</div>
        <el-menu-item v-if="auth.isSuper" index="/dashboard">
          <el-icon><DataAnalysis /></el-icon
          ><template #title>数据看板</template>
        </el-menu-item>
        <el-menu-item index="/invoke">
          <el-icon><ChatDotRound /></el-icon
          ><template #title>模型调试台</template>
        </el-menu-item>

        <template v-if="showOrgGroup">
          <div v-if="!collapsed" class="menu-group">资源管理</div>
          <el-menu-item v-if="auth.isSuper" index="/channels">
            <el-icon><Coin /></el-icon><template #title>渠道管理</template>
          </el-menu-item>
          <el-menu-item v-if="auth.hasPerm('dept:member') || auth.isManager" index="/users">
            <el-icon><User /></el-icon><template #title>用户管理</template>
          </el-menu-item>
          <el-menu-item v-if="auth.hasPerm('dept:info') || auth.hasPerm('dept:member') || auth.isManager" index="/departments">
            <el-icon><OfficeBuilding /></el-icon
            ><template #title>部门管理</template>
          </el-menu-item>
          <el-menu-item v-if="auth.isSuper || auth.isManager" index="/permissions">
            <el-icon><Key /></el-icon
            ><template #title>权限维护</template>
          </el-menu-item>
        </template>

        <template v-if="auth.hasPerm('log:view') || auth.isSuper">
          <div v-if="!collapsed" class="menu-group">监控告警</div>
          <el-menu-item v-if="auth.hasPerm('log:view')" index="/logs">
            <el-icon><Document /></el-icon><template #title>调用日志</template>
          </el-menu-item>
          <el-menu-item v-if="auth.isSuper" index="/alerts">
            <el-icon><Bell /></el-icon>
            <template #title>
              <span>告警中心</span>
              <el-badge v-if="unreadAlerts > 0" :value="unreadAlerts" :max="99" class="menu-badge" />
            </template>
          </el-menu-item>
        </template>

        <template v-if="auth.hasPerm('policy:manage')">
          <div v-if="!collapsed" class="menu-group">策略配置</div>
          <el-menu-item index="/policies">
            <el-icon><Aim /></el-icon><template #title>限流熔断</template>
          </el-menu-item>
        </template>

        <template v-if="auth.hasPerm('prompt:manage') || auth.hasPerm('prompt:view')">
          <div v-if="!collapsed" class="menu-group">Prompt 工程</div>
          <el-menu-item v-if="auth.hasPerm('prompt:manage')" index="/prompt/templates">
            <el-icon><EditPen /></el-icon><template #title>Prompt 模板</template>
          </el-menu-item>
          <el-menu-item v-if="auth.hasPerm('prompt:view')" index="/prompt/metrics">
            <el-icon><DataLine /></el-icon><template #title>Prompt 监控</template>
          </el-menu-item>
        </template>

        <template v-if="auth.hasPerm('ctx:view')">
          <div v-if="!collapsed" class="menu-group">Context 工程</div>
          <el-menu-item index="/context/events">
            <el-icon><Search /></el-icon><template #title>检索与快照</template>
          </el-menu-item>
          <el-menu-item index="/context/metrics">
            <el-icon><Histogram /></el-icon><template #title>Context 监控</template>
          </el-menu-item>
        </template>

        <el-menu-item index="/profile">
          <el-icon><Postcard /></el-icon
          ><template #title>个人中心</template>
        </el-menu-item>
      </el-menu>

      <div class="collapse-btn" @click="collapsed = !collapsed">
        <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        <span v-if="!collapsed">收起</span>
      </div>
    </el-aside>

    <el-container>
      <el-header class="topbar" height="52px">
        <div class="topbar-right">
          <span class="clock">{{ now }} · UTC+8</span>
          <el-dropdown @command="onCommand">
            <div class="user-chip">
              <el-avatar :size="28" class="avatar">{{ avatarText }}</el-avatar>
              <span class="username">{{ auth.user?.username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled
                  >权限: {{ permissionText }}</el-dropdown-item
                >
                <el-dropdown-item command="profile" divided
                  >个人中心</el-dropdown-item
                >
                <el-dropdown-item command="logout"
                  >退出登录</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import dayjs from "dayjs";
import { useAuthStore } from "@/stores/auth";
import { alertApi } from "@/api";

const auth = useAuthStore();
const router = useRouter();
const collapsed = ref(false);
const now = ref(dayjs().format("HH:mm:ss"));
const unreadAlerts = ref(0);
let timer = 0;
let alertTimer = 0;

/** 超管轮询未读告警数,驱动菜单红点(30s 一次) */
async function pollUnreadAlerts() {
  if (!auth.isSuper) return;
  try {
    const { data } = await alertApi.unreadCount();
    unreadAlerts.value = data.data;
  } catch {
    // 轮询失败(如未登录/网关未起)静默,下轮再试
  }
}

onMounted(() => {
  timer = window.setInterval(
    () => (now.value = dayjs().format("HH:mm:ss")),
    1000,
  );
  pollUnreadAlerts();
  alertTimer = window.setInterval(pollUnreadAlerts, 30_000);
});
onUnmounted(() => {
  clearInterval(timer);
  clearInterval(alertTimer);
});

const avatarText = computed(() =>
  (auth.user?.username || "U").slice(0, 1).toUpperCase(),
);
const showOrgGroup = computed(
  () =>
    auth.isSuper ||
    auth.hasPerm("dept:member") ||
    auth.hasPerm("dept:info") ||
    auth.isManager,
);
const DEPT_POSITION_TEXT: Record<string, string> = {
  MANAGER: "经理",
  DEPUTY: "副经理",
  LEADER: "组长",
  MEMBER: "组员",
};
const permissionText = computed(() => {
  if (auth.isSuper) return "超级管理员";
  const dept = auth.user?.department?.name;
  const pos = auth.user?.deptPosition
    ? DEPT_POSITION_TEXT[auth.user.deptPosition]
    : null;
  return [dept, pos].filter(Boolean).join(" · ") || "普通用户";
});

function onCommand(cmd: string) {
  if (cmd === "profile") {
    router.push("/profile");
  } else if (cmd === "logout") {
    auth.logout();
    router.push("/login");
  }
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}
.sidebar {
  background: #fff;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  cursor: pointer;
}
.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.logo-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2d3d;
  line-height: 1.2;
}
.logo-sub {
  font-size: 9px;
  color: #a0a5b0;
  letter-spacing: 0.5px;
  transform: scale(0.9);
  transform-origin: left;
}
.menu {
  flex: 1;
  padding: 4px 8px;
  overflow-y: auto;
}
.menu-group {
  font-size: 12px;
  color: #b0b6c3;
  padding: 12px 12px 4px;
}
.menu-badge {
  margin-left: 8px;
  vertical-align: 2px;
}
.collapse-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 20px;
  color: #909399;
  font-size: 13px;
  border-top: 1px solid #f2f3f5;
  cursor: pointer;
}
.collapse-btn:hover {
  color: var(--gw-primary);
}
.topbar {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.clock {
  font-size: 13px;
  color: #606266;
  font-variant-numeric: tabular-nums;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.avatar {
  background: #67c23a;
  font-size: 13px;
}
.username {
  font-size: 13px;
  color: #303133;
}
.main {
  padding: 16px;
  overflow-y: auto;
  background: var(--gw-bg);
}
</style>
