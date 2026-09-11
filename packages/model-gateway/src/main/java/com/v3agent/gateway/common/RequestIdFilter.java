package com.v3agent.gateway.common;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

/**
 * 全链路请求 ID 过滤器:优先沿用上游(NestJS / ai-service)传入的 X-Request-Id,
 * 否则生成 UUID。写入 MDC 供日志模板输出,并回写响应头。
 * 排障时一个 id 可贯穿 NestJS → ai-service → model-gateway 三层日志与 invoke_logs。
 */
@Component
@Order(1)
public class RequestIdFilter implements Filter {

    public static final String HEADER = "X-Request-Id";
    public static final String MDC_KEY = "requestId";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest req = (HttpServletRequest) request;
        HttpServletResponse res = (HttpServletResponse) response;
        String incoming = req.getHeader(HEADER);
        String requestId = (incoming == null || incoming.isBlank())
                ? UUID.randomUUID().toString()
                : incoming.trim();
        if (requestId.length() > 64) {
            requestId = requestId.substring(0, 64);
        }
        try {
            MDC.put(MDC_KEY, requestId);
            res.setHeader(HEADER, requestId);
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
