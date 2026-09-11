package com.v3agent.rag.chat;

import com.v3agent.rag.common.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/rag/kbs/{kbId}/chat")
@RequiredArgsConstructor
public class RagChatController {

    private final RagChatService ragChatService;

    @PostMapping
    public ApiResponse<ChatResponse> chat(@PathVariable String kbId,
                                          @RequestBody @Valid ChatRequest req) {
        return ApiResponse.ok(ragChatService.ask(kbId, req.question()), "回答生成成功");
    }
}
