package com.v3agent.gateway.common;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 健康检查(存活 + 依赖探测):路径不在 /api /v1 拦截范围内,无需鉴权。
 * DB 不通时返回 503,便于启动脚本/负载均衡摘除"活着但废了"的实例。
 */
@RestController
@RequiredArgsConstructor
public class HealthController {

    private final DataSource dataSource;

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> detail = new LinkedHashMap<>();
        boolean ok = true;
        try (Connection conn = dataSource.getConnection()) {
            ok = conn.isValid(2);
            detail.put("db", ok ? "up" : "down");
        } catch (Exception e) {
            ok = false;
            detail.put("db", "down");
            detail.put("dbError", e.getClass().getSimpleName());
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", ok ? "ok" : "degraded");
        body.put("detail", detail);
        body.put("time", OffsetDateTime.now().toString());
        return ResponseEntity
                .status(ok ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE)
                .body(body);
    }
}
