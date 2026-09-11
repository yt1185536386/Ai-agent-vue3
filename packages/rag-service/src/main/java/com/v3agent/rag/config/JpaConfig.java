package com.v3agent.rag.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.boot.autoconfigure.domain.EntityScan;

/**
 * 内存模式下的 JPA 扫描配置：排除 pgvector 专属实体/仓储包。
 * pgvector 模式使用 Spring Boot 默认扫描（包含 com.v3agent.rag.vector.pgvector）。
 */
@Profile("!pgvector")
@Configuration
@EntityScan(basePackages = {
        "com.v3agent.rag.kb",
        "com.v3agent.rag.doc",
        "com.v3agent.rag.user"
})
@EnableJpaRepositories(basePackages = {
        "com.v3agent.rag.kb",
        "com.v3agent.rag.doc",
        "com.v3agent.rag.user"
})
public class JpaConfig {
}
