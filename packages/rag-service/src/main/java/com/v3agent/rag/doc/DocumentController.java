package com.v3agent.rag.doc;

import com.v3agent.rag.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/rag/kbs/{kbId}/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @PostMapping
    public ApiResponse<DocumentResponse> upload(@PathVariable String kbId,
                                                @RequestParam("file") MultipartFile file) {
        return ApiResponse.ok(documentService.upload(kbId, file), "上传文档成功");
    }

    @GetMapping
    public ApiResponse<List<DocumentResponse>> list(@PathVariable String kbId) {
        return ApiResponse.ok(documentService.list(kbId), "查询文档列表成功");
    }

    @DeleteMapping("/{docId}")
    public ApiResponse<Void> delete(@PathVariable String kbId,
                                    @PathVariable String docId) {
        documentService.delete(kbId, docId);
        return ApiResponse.ok("删除文档成功");
    }
}
