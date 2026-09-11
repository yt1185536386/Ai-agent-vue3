package com.v3agent.rag.kb;

import jakarta.validation.constraints.NotBlank;

public record KnowledgeBaseRequest(
        @NotBlank(message = "知识库名称不能为空") String name,
        String description
) {}
