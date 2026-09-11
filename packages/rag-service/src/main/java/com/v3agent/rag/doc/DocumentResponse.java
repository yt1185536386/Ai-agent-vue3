package com.v3agent.rag.doc;

import java.time.LocalDateTime;

public record DocumentResponse(
        String id,
        String knowledgeBaseId,
        String fileName,
        Integer status,
        Integer pageCount,
        String errorMessage,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {}
