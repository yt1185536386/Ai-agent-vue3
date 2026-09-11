package com.v3agent.rag.kb;

import com.v3agent.rag.common.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/rag/kbs")
@RequiredArgsConstructor
public class KnowledgeBaseController {

    private final KnowledgeBaseService kbService;

    @PostMapping
    public ApiResponse<KnowledgeBaseEntity> create(@RequestBody @Valid KnowledgeBaseRequest req) {
        KnowledgeBaseEntity kb = kbService.create(req.name(), req.description());
        return ApiResponse.ok(kb, "创建知识库成功");
    }

    @GetMapping
    public ApiResponse<List<KnowledgeBaseEntity>> list() {
        return ApiResponse.ok(kbService.listMine(), "查询知识库列表成功");
    }

    @GetMapping("/{id}")
    public ApiResponse<KnowledgeBaseEntity> get(@PathVariable String id) {
        return ApiResponse.ok(kbService.getMine(id), "查询知识库成功");
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        kbService.delete(id);
        return ApiResponse.ok("删除知识库成功");
    }
}
