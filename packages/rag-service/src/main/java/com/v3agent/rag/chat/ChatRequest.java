package com.v3agent.rag.chat;

import jakarta.validation.constraints.NotBlank;

public record ChatRequest(
        @NotBlank(message = "问题不能为空") String question
) {}
