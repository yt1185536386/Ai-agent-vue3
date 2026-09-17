package com.v3agent.gateway.config;

import com.v3agent.gateway.auth.AuthInterceptor;
import com.v3agent.gateway.auth.ServiceKeyInterceptor;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {

    private final AuthInterceptor authInterceptor;
    private final ServiceKeyInterceptor serviceKeyInterceptor;

    @Value("${gateway.cors.allowed-origins:http://localhost:26012,http://localhost:26013}")
    private String allowedOrigins;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // /api/** 管理端: NestJS 签发的 JWT(共享密钥,只校验不签发)
        registry.addInterceptor(authInterceptor)
                .addPathPatterns("/api/**");
        // /v1/** OpenAI 兼容入口: 内部服务密钥 + X-User-Id 透传,不校验用户 JWT
        registry.addInterceptor(serviceKeyInterceptor)
                .addPathPatterns("/v1/**");
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // 跨域白名单(逗号分隔,支持 origin pattern):
        // 原先 allowedOriginPatterns("*") + allowCredentials 等于全站放开,企业安全扫描必挂
        String[] origins = java.util.Arrays.stream(allowedOrigins.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toArray(String[]::new);
        registry.addMapping("/**")
                .allowedOriginPatterns(origins.length > 0 ? origins : new String[]{"http://localhost:26012", "http://localhost:26013"})
                .allowedMethods("*")
                .allowedHeaders("*")
                .allowCredentials(true);
    }
}
