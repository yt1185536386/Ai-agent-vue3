package com.v3agent.rag.search;

import jakarta.validation.constraints.NotBlank;

/**
 * 检索原语请求。
 *
 * @param knowledgeBaseId 知识库 ID；为空时检索当前用户拥有的全部知识库合集
 * @param topK            返回条数上限；缺省取 rag.retrieval.top-k
 */
public record SearchRequest(
        @NotBlank(message = "检索问题不能为空") String question,
        String knowledgeBaseId,
        Integer topK
) {}