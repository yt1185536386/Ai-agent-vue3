package com.v3agent.rag.vector;

import java.util.List;

/**
 * 向量存储抽象：保存/删除文档块，并按向量相似度检索 Top-K。
 */
public interface VectorStore {

    /**
     * 保存一个文档的所有文本块及其向量。
     *
     * @param documentId      文档 ID
     * @param knowledgeBaseId 知识库 ID
     * @param chunks          文本块列表
     */
    void saveChunks(String documentId, String knowledgeBaseId, List<ChunkData> chunks);

    /**
     * 删除指定文档的所有文本块。
     */
    void deleteByDocumentId(String documentId);

    /**
     * 按向量相似度检索知识库中的 Top-K 文本块（按 L2 距离升序）。
     */
    List<ChunkData> search(String knowledgeBaseId, float[] queryVector, int topK);
}
