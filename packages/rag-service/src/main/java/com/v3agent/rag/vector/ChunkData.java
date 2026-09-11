package com.v3agent.rag.vector;

/**
 * 文本块 + 向量的通用表示，屏蔽底层存储（pgvector / in-memory）。
 */
public record ChunkData(
        String id,
        String documentId,
        String knowledgeBaseId,
        int chunkIndex,
        String content,
        float[] embedding
) {}
