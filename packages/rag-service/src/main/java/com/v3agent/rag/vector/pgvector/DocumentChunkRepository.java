package com.v3agent.rag.vector.pgvector;

import com.pgvector.PGvector;
import org.springframework.context.annotation.Profile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

/**
 * 文档块 JPA 仓储，仅在 pgvector 模式下启用。
 */
@Profile("pgvector")
public interface DocumentChunkRepository extends JpaRepository<DocumentChunkEntity, String> {

    /**
     * 按向量距离检索知识库中最近的 Top-K 文本块。
     * 参数 vector 使用 PGvector 类型，可直接绑定到 pgvector 算子 <->。
     */
    @Query(value = "SELECT * FROM document_chunks " +
            "WHERE knowledge_base_id = :kbId " +
            "ORDER BY embedding <-> :vector " +
            "LIMIT :topK", nativeQuery = true)
    List<DocumentChunkEntity> findTopKByKnowledgeBaseId(@Param("kbId") String knowledgeBaseId,
                                                        @Param("vector") PGvector vector,
                                                        @Param("topK") int topK);

    void deleteByDocumentId(String documentId);
}
