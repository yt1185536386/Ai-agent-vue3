import { computed, ref } from "vue";
import { clearToken, loadAuth, parseJwt, setToken } from "./auth";
import { extractErrorMessage, post } from "../../axios";

export function useAuthMixin() {
  const auth = ref(loadAuth());
  const isRegister = ref(false);
  const authForm = ref({ username: "", password: "" });
  const authError = ref("");
  const isAuthLoading = ref(false);

  const isLoggedIn = computed(() => !!auth.value?.token);

  const updateFromToken = (token: string) => {
    setToken(token);
    const payload = parseJwt(token);
    if (payload?.sub && payload?.username) {
      auth.value = {
        token,
        userId: payload.sub,
        username: payload.username,
        isSuperAdmin: payload.isSuperAdmin === true,
        jobLevelRank: payload.jobLevelRank ?? null,
        jobLevelName: payload.jobLevelName ?? null,
      };
    } else {
      auth.value = null;
    }
  };

  const submitAuth = async () => {
    authError.value = "";
    const endpoint = isRegister.value ? "auth/register" : "auth/login";
    isAuthLoading.value = true;
    try {
      const json = await post<{ access_token: string }>(endpoint, {
        username: authForm.value.username,
        password: authForm.value.password,
      });
      if (!json.access_token) {
        throw new Error("响应中缺少 token");
      }
      updateFromToken(json.access_token);
      authForm.value = { username: "", password: "" };
    } catch (e: any) {
      authError.value = `失败:${extractErrorMessage(e)}`;
    } finally {
      isAuthLoading.value = false;
    }
  };

  const logout = () => {
    clearToken();
    auth.value = null;
    authForm.value = { username: "", password: "" };
    authError.value = "";
  };

  return {
    auth,
    isLoggedIn,
    isRegister,
    authForm,
    authError,
    isAuthLoading,
    submitAuth,
    logout,
  };
}
