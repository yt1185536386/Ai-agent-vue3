package com.v3agent.gateway.invoke;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.v3agent.gateway.auth.AuthContext;
import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

/** 模型调用入口(/v1/** 由 ServiceKeyInterceptor 做内部服务鉴权) */
@RestController
@RequiredArgsConstructor
public class InvokeController {

    private final InvokeService invokeService;

    /** 管理端调试台调用(JWT 鉴权,统一响应体包装) */
    @PostMapping("/api/invoke/chat")
    @RequirePermission(RequirePermission.AUTH)
    public ApiResponse<JsonNode> chat(@RequestBody ObjectNode payload) {
        return ApiResponse.ok(invokeService.chatCompletions(AuthContext.require(), payload, null), "模型调用成功");
    }

    /**
     * OpenAI 兼容入口: ai-service 等内部调用方带 X-Service-Key + X-User-Id,
     * 限流 / 熔断 / 计量由网关透明完成。stream=true 时 SSE 原生透传。
     * X-Channel-Key 头可按渠道 key 精确路由(缺省按模型列表匹配)。
     */
    @PostMapping("/v1/chat/completions")
    public ResponseEntity<?> openAiCompatible(@RequestBody ObjectNode payload,
                                   @RequestHeader(value = "X-Channel-Key", required = false) String channelKey,
                                   jakarta.servlet.http.HttpServletResponse response) throws java.io.IOException {
        if (payload.path("stream").asBoolean(false)) {
            // 流式: 由 service 直接写 response(声明 Object/ResponseEntity 返回类型时
            // StreamingResponseBody 会走到 converter 链报错),此处返回 null 表示已提交
            invokeService.chatCompletionsStream(AuthContext.require(), payload, channelKey, response);
            return null;
        }
        return ResponseEntity.ok(invokeService.chatCompletions(AuthContext.require(), payload, channelKey));
    }

    /** embeddings 透传(RAG 向量化),计量按输入文本粗估 */
    @PostMapping("/v1/embeddings")
    public JsonNode embeddings(@RequestBody ObjectNode payload,
                               @RequestHeader(value = "X-Channel-Key", required = false) String channelKey) {
        return invokeService.embeddings(AuthContext.require(), payload, channelKey);
    }

    /** 模型列表: 带 X-Channel-Key 时透传该渠道上游 /models,否则按本地渠道配置聚合 */
    @GetMapping("/v1/models")
    public JsonNode models(@RequestHeader(value = "X-Channel-Key", required = false) String channelKey) {
        return invokeService.listModels(channelKey);
    }
}
