package com.v3agent.gateway.repo;

import org.springframework.web.client.RestClient;

import java.net.http.HttpRequest;

/**
 * 渠道上游认证:按 ChannelEntity.authType 把 API Key 附到请求上。
 * <ul>
 *   <li>bearer      → Authorization: Bearer &lt;key&gt;(OpenAI 兼容默认)</li>
 *   <li>x-api-key   → x-api-key: &lt;key&gt;(Anthropic 风格)</li>
 *   <li>api-key     → api-key: &lt;key&gt;(Azure OpenAI 头风格)</li>
 *   <li>query       → URL 追加 ?api-key=&lt;key&gt;(Azure OpenAI 参数风格;由调用方拼 URI)</li>
 *   <li>none        → 不带认证(内网免认证上游)</li>
 * </ul>
 */
public final class ChannelAuth {

    public static final String BEARER = "bearer";
    public static final String X_API_KEY = "x-api-key";
    public static final String API_KEY = "api-key";
    public static final String QUERY = "query";
    public static final String NONE = "none";

    private ChannelAuth() {}

    /** RestClient 请求头认证(query 类型改用 authUri 拼参数,这里不重复加头) */
    public static RestClient.RequestHeadersSpec<?> apply(RestClient.RequestHeadersSpec<?> spec, ChannelEntity c) {
        String type = authType(c);
        return switch (type) {
            case X_API_KEY -> spec.header("x-api-key", c.getApiKey());
            case API_KEY -> spec.header("api-key", c.getApiKey());
            case NONE, QUERY -> spec;
            default -> spec.header("Authorization", "Bearer " + c.getApiKey());
        };
    }

    /** JDK HttpRequest 认证(流式转发路径用) */
    public static HttpRequest.Builder apply(HttpRequest.Builder builder, ChannelEntity c) {
        String type = authType(c);
        return switch (type) {
            case X_API_KEY -> builder.header("x-api-key", c.getApiKey());
            case API_KEY -> builder.header("api-key", c.getApiKey());
            case NONE, QUERY -> builder;
            default -> builder.header("Authorization", "Bearer " + c.getApiKey());
        };
    }

    /** query 认证:把 api-key 拼进 URI(保持已有 query string) */
    public static String authUri(String uri, ChannelEntity c) {
        if (!QUERY.equals(authType(c))) {
            return uri;
        }
        String sep = uri.contains("?") ? "&" : "?";
        return uri + sep + "api-key=" + c.getApiKey();
    }

    /** 空值回退 bearer(老数据无此列时行为与改造前一致) */
    public static String authType(ChannelEntity c) {
        String t = c.getAuthType();
        return (t == null || t.isBlank()) ? BEARER : t.trim();
    }
}
