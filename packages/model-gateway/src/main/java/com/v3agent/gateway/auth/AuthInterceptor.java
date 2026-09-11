package com.v3agent.gateway.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.v3agent.gateway.common.ApiResponse;
import com.v3agent.gateway.perm.PermissionService;
import com.v3agent.gateway.user.UserEntity;
import com.v3agent.gateway.user.UserRepository;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 管理端鉴权拦截器(/api/**): 解析 NestJS 网关签发的 Bearer Token
 * (共享 JWT 密钥,本网关只校验不签发),并按 @RequirePermission 做权限码校验。
 * 与 NestJS PermissionGuard 对齐:从共享 users 表加载用户并
 * 解析有效权限码(个人绑定逐项覆盖职级绑定,超管全通)。
 * 用户+权限码走 30s TTL 缓存(本网关不写权限数据,NestJS 侧写后最迟 30s 生效)。
 * 默认拒绝:/api/** 下未标注 @RequirePermission 的接口一律 401,
 * 避免新增接口忘加注解导致裸奔。
 */
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;
    private final UserRepository userRepository;
    private final PermissionService permissionService;

    /** 用户+有效权限码快照缓存:30s TTL(权限写操作都在 NestJS 侧,靠 TTL 失效即可) */
    private record CachedAuth(UserEntity user, Set<String> codes, long at) {}

    private final java.util.concurrent.ConcurrentHashMap<String, CachedAuth> authCache =
            new java.util.concurrent.ConcurrentHashMap<>();

    private static final long AUTH_CACHE_TTL_MS = 30_000;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        if (!(handler instanceof HandlerMethod method)) {
            return true;
        }
        String header = request.getHeader("Authorization");
        String token = (header != null && header.startsWith("Bearer ")) ? header.substring(7) : null;
        CachedAuth cached = null;
        if (token != null) {
            Claims claims = jwtUtil.parse(token);
            if (claims != null) {
                cached = loadAuth(claims.getSubject());
            }
        }
        UserEntity freshUser = cached == null ? null : cached.user();

        // 类级 + 方法级 @RequirePermission,方法级优先
        RequirePermission required = method.getMethodAnnotation(RequirePermission.class);
        if (required == null) {
            required = method.getBeanType().getAnnotation(RequirePermission.class);
        }
        if (required == null) {
            // 默认拒绝:/api/** 未标注鉴权要求的接口不对外开放
            writeError(response, 401, "未登录或登录已过期");
            return false;
        }

        if (freshUser == null) {
            writeError(response, 401, "未登录或登录已过期");
            return false;
        }
        if (freshUser.getStatus() != null && freshUser.getStatus() != 1) {
            writeError(response, 403, "账号已被禁用");
            return false;
        }

        boolean isSuper = Boolean.TRUE.equals(freshUser.getIsSuperAdmin());
        String need = required.value();
        if (!isSuper && !RequirePermission.AUTH.equals(need)) {
            if (RequirePermission.SUPER.equals(need)) {
                writeError(response, 403, "仅超级管理员可执行该操作");
                return false;
            }
            Set<String> codes = cached.codes();
            if (!codes.contains(need)) {
                writeError(response, 403, "没有访问权限");
                return false;
            }
            AuthContext.set(new CurrentUser(freshUser.getId(), freshUser.getUsername(), false, codes));
            return true;
        }
        AuthContext.set(new CurrentUser(freshUser.getId(), freshUser.getUsername(), isSuper,
                isSuper ? cached.codes() : Set.of()));
        return true;
    }

    /** 加载用户与有效权限码(带 30s TTL 缓存);用户不存在返回 null */
    private CachedAuth loadAuth(String userId) {
        if (userId == null || userId.isBlank()) {
            return null;
        }
        CachedAuth hit = authCache.get(userId);
        long now = System.currentTimeMillis();
        if (hit != null && now - hit.at() < AUTH_CACHE_TTL_MS) {
            return hit;
        }
        UserEntity user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return null;
        }
        Set<String> codes = permissionService.resolveCodes(user);
        CachedAuth fresh = new CachedAuth(user, codes, now);
        authCache.put(userId, fresh);
        // 简单防膨胀:超量时整体清空(正常规模下用户数远小于该值)
        if (authCache.size() > 10_000) {
            authCache.clear();
        }
        return fresh;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        AuthContext.clear();
    }

    private void writeError(HttpServletResponse response, int code, String message) throws IOException {
        response.setStatus(code);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(objectMapper.writeValueAsString(ApiResponse.error(code, message)));
    }
}
