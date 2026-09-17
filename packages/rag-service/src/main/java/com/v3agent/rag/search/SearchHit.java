package com.v3agent.rag.search;

/**
 * 检索命中的单个文本块（只返回片段，不经过模型，供 Agent 等消费方编排）。
 *
 * @param chunkId     文本块 ID
 * @param documentId  所属文档 ID
 * @param chunkIndex  文本块在文档内的序号
 * @param content     文本块内容
 * @param distance    L2 检索距离（越小越近）
 */
public record SearchHit(
        String chunkId,
        String documentId,
        Integer chunkIndex,
        String content,
        Double distance
) {}