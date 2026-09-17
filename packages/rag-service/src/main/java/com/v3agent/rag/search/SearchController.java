package com.v3agent.rag.search;

import com.v3agent.rag.common.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 检索原语入口：供 ai-service 等消费方按需检索知识库片段（不经过模型）。
 * 走 /api/rag/** 统一鉴权；ai-service 以 X-Service-Key 内部服务密钥放行。
 */
@RestController
@RequestMapping("/api/rag/search")
@RequiredArgsConstructor
public class SearchController {

    private final SearchService searchService;

    @PostMapping
    public ApiResponse<List<SearchHit>> search(@RequestBody @Valid SearchRequest req) {
        return ApiResponse.ok(searchService.search(req), "检索成功");
    }
}