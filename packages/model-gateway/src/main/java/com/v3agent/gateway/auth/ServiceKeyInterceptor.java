package com.v3agent.gateway.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 内部服务鉴权拦截器(/v1/** OpenAI 兼容入口):
 * 校验 X-Service-Key(与 NestJS↔ai-service 同款内部密钥),
 * 用户身份由调用方经 X-User-Id / X-Username 透传,仅作限流/计量维度,
 * 本网关不再对用户做权限判断(用户权限权威在 NestJS 业务网关)。
 */
@Component
public class ServiceKeyInterceptor implements HandlerInterceptor {

    private final String serviceKey;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ServiceKeyInterceptor(@Value("${gateway.service-key:}") String serviceKey) {
        this.serviceKey = serviceKey;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        if (serviceKey.isBlank()) {
            writeError(response, 500, "服务未配置 gateway.service-key,无法安全接收内部调用");
            return false;
        }
        // OpenAI 客户端约定把 apiKey 放在 Authorization: Bearer 里,
        // 内部调用方(ai-service)即如此;X-Service-Key 头为显式方式,两者皆可
        String key = request.getHeader("X-Service-Key");
        if (key == null || key.isBlank()) {
            String auth = request.getHeader("Authorization");
            if (auth != null && auth.startsWith("Bearer ")) {
                key = auth.substring(7);
            }
        }
        if (!constantTimeEquals(serviceKey, key)) {
            writeError(response, 401, "Invalid service key");
            return false;
        }
        String userId = request.getHeader("X-User-Id");
        // 用户名由调用方 URL 编码后透传(中文无法直接放 HTTP 头)
        String username = decode(request.getHeader("X-Username"));
        AuthContext.set(new CurrentUser(
                (userId == null || userId.isBlank()) ? "internal" : userId,
                (username == null || username.isBlank()) ? (userId == null ? "internal" : userId) : username,
                false, Set.of()));
        return true;
    }

    private String decode(String s) {
        if (s == null) {
            return null;
        }
        try {
            return java.net.URLDecoder.decode(s, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return s;
        }
    }

    /** 常量时间比较,避免逐字符比较的时序侧信道 */
    private boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) {
            return false;
        }
        return java.security.MessageDigest.isEqual(
                a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        AuthContext.clear();
    }

    /** /v1 入口面向 OpenAI SDK,错误体用 OpenAI 兼容结构(SDK 只解析 error 字段) */
    private void writeError(HttpServletResponse response, int code, String message) throws IOException {
        response.setStatus(code);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        ObjectNode error = objectMapper.createObjectNode();
        error.put("message", message);
        error.put("type", "gateway_auth_error");
        error.putNull("param");
        error.putNull("code");
        ObjectNode body = objectMapper.createObjectNode();
        body.set("error", error);
        response.getWriter().write(objectMapper.writeValueAsString(body));
    }
}
