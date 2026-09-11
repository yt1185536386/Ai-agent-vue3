package com.v3agent.rag.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.v3agent.rag.common.ApiResponse;
import com.v3agent.rag.user.UserEntity;
import com.v3agent.rag.user.UserRepository;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * RAG 管理端鉴权拦截器（/api/rag/**）。
 * 解析 model-gateway / NestJS 签发的 Bearer Token；当 rag-service 与网关共用 users 表时，
 * 以 DB 为准校验用户状态，禁用/权限变更立即生效。未共享用户表时，回退为仅校验 JWT 签名。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;
    private final UserRepository userRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        String header = request.getHeader("Authorization");
        String token = (header != null && header.startsWith("Bearer ")) ? header.substring(7) : null;

        if (token == null) {
            writeError(response, 401, "未登录或登录已过期");
            return false;
        }

        Claims claims = jwtUtil.parse(token);
        if (claims == null) {
            writeError(response, 401, "未登录或登录已过期");
            return false;
        }

        String userId = claims.getSubject();
        String username = claims.get("username", String.class);
        if (username == null || username.isBlank()) {
            username = userId;
        }

        UserEntity freshUser = userRepository.findById(userId).orElse(null);
        if (freshUser != null) {
            if (freshUser.getStatus() != null && freshUser.getStatus() != 1) {
                writeError(response, 403, "账号已被禁用");
                return false;
            }
            AuthContext.set(new CurrentUser(freshUser.getId(), freshUser.getUsername()));
            return true;
        }

        // 未共享 users 表时退化为 JWT 签名校验
        log.warn("users 表中未找到用户 {}，退化为 JWT 声明校验", userId);
        AuthContext.set(new CurrentUser(userId, username));
        return true;
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
