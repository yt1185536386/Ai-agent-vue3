package com.v3agent.rag.vector;

import com.pgvector.PGvector;
import com.v3agent.rag.vector.pgvector.DocumentChunkEntity;
import com.v3agent.rag.vector.pgvector.DocumentChunkRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 基于 PostgreSQL + pgvector 的向量存储实现。
 */
@Component
@Profile("pgvector")
@RequiredArgsConstructor
public class PgVectorStore implements VectorStore {

    private final DocumentChunkRepository chunkRepository;

    @Override
    @Transactional
    public void saveChunks(String documentId, String knowledgeBaseId, List<ChunkData> chunks) {
        List<DocumentChunkEntity> entities = chunks.stream()
                .map(chunk -> {
                    DocumentChunkEntity entity = new DocumentChunkEntity();
                    entity.setId(chunk.id() == null ? UUID.randomUUID().toString() : chunk.id());
                    entity.setDocumentId(documentId);
                    entity.setKnowledgeBaseId(knowledgeBaseId);
                    entity.setChunkIndex(chunk.chunkIndex());
                    entity.setContent(chunk.content());
                    entity.setEmbedding(chunk.embedding());
                    return entity;
                })
                .toList();
        chunkRepository.saveAll(entities);
    }

    @Override
    @Transactional
    public void deleteByDocumentId(String documentId) {
        chunkRepository.deleteByDocumentId(documentId);
    }

    @Override
    public List<ChunkData> search(String knowledgeBaseId, float[] queryVector, int topK) {
        return chunkRepository.findTopKByKnowledgeBaseId(knowledgeBaseId, new PGvector(queryVector), topK)
                .stream()
                .map(this::toChunkData)
                .collect(Collectors.toList());
    }

    private ChunkData toChunkData(DocumentChunkEntity entity) {
        return new ChunkData(
                entity.getId(),
                entity.getDocumentId(),
                entity.getKnowledgeBaseId(),
                entity.getChunkIndex(),
                entity.getContent(),
                entity.getEmbedding()
        );
    }
}
