package com.v3agent.rag.chat;

import java.util.List;

public record ChatResponse(
        String answer,
        List<String> references
) {}
