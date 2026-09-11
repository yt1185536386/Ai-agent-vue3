// @ts-nocheck
/**
 * AgentMode 主组件入口:
 * 通过 setup() 将 mixin.ts 与 auth.ts 中的状态与方法合并,供 index.vue 模板使用。
 */
import { defineComponent } from "vue";
import { useRouter } from "vue-router";
import { useAgentMixin } from "./mixin";
import { useAuthMixin } from "./auth-mixin";

export default defineComponent({
  name: "AgentMode",
  setup() {
    const router = useRouter();
    const auth = useAuthMixin();
    const agent = useAgentMixin(auth);

    /** 未登录时点击"用户登录":关闭菜单并跳转登录页 */
    const goLogin = () => {
      agent.userMenuOpen.value = false;
      router.push("/login");
    };

    /** 退出登录:清除状态后跳转登录页(与路由守卫的未登录行为一致) */
    const logout = () => {
      auth.logout();
      agent.userMenuOpen.value = false;
      router.push("/login");
    };

    return { ...agent, ...auth, goLogin, logout };
  },
});
