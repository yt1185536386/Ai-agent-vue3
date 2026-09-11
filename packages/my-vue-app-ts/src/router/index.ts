import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized, NavigationGuardNext } from "vue-router";
import { loadAuth } from "../view/AgentMode/auth";

const routes = [
  {
    path: "/",
    name: "Agent",
    // 懒加载:登录页与主界面分包,首屏只加载当前路由
    component: () => import("../view/AgentMode/index.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("../view/Login/index.vue"),
    meta: { public: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
  const auth = loadAuth();
  const isLoggedIn = !!auth?.token;

  if (to.meta.requiresAuth && !isLoggedIn) {
    next("/login");
    return;
  }

  if (to.path === "/login" && isLoggedIn) {
    next("/");
    return;
  }

  next();
});

export default router;
