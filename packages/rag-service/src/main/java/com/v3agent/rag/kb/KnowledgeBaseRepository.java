package com.v3agent.rag.kb;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface KnowledgeBaseRepository extends JpaRepository<KnowledgeBaseEntity, String> {

    List<KnowledgeBaseEntity> findByOwnerUserIdOrderByCreatedAtDesc(String ownerUserId);
}
