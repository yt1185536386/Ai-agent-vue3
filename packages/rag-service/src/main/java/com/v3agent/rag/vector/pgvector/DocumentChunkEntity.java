package com.v3agent.rag.vector.pgvector;

import com.pgvector.PGvector;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Data;
import org.springframework.context.annotation.Profile;

import java.time.LocalDateTime;

/**
 * 文档块：PDF 切分后的文本片段及其 Embedding 向量。
 * 仅在 pgvector 模式下使用；内存模式由 {@link com.v3agent.rag.vector.InMemoryVectorStore} 存储。
 */
@Data
@Entity
@Profile("pgvector")
@Table(name = "document_chunks")
public class DocumentChunkEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(length = 36)
    private String id;

    @Column(nullable = false, length = 36)
    private String documentId;

    @Column(nullable = false, length = 36)
    private String knowledgeBaseId;

    @Column(nullable = false)
    private Integer chunkIndex;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String content;

    /** pgvector 向量列；维度需与 embedding 模型一致，默认 1536 */
    @Convert(converter = VectorConverter.class)
    @Column(nullable = false, columnDefinition = "vector(1536)")
    private float[] embedding;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = createdAt;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
