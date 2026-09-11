package com.v3agent.rag.doc;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DocumentRepository extends JpaRepository<DocumentEntity, String> {

    List<DocumentEntity> findByKnowledgeBaseIdOrderByCreatedAtDesc(String knowledgeBaseId);
}
