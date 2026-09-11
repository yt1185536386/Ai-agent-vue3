package com.v3agent.rag.doc;

import com.v3agent.rag.auth.AuthContext;
import com.v3agent.rag.chat.EmbeddingClient;
import com.v3agent.rag.common.BizException;
import com.v3agent.rag.kb.KnowledgeBaseService;
import com.v3agent.rag.vector.ChunkData;
import com.v3agent.rag.vector.VectorStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

/**
 * 文档上传：PDF 解析 → 切分 → Embedding → 存入向量存储。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentService {

    private final KnowledgeBaseService kbService;
    private final DocumentRepository documentRepository;
    private final VectorStore vectorStore;
    private final PdfParseService pdfParseService;
    private final TextSplitter textSplitter;
    private final EmbeddingClient embeddingClient;

    @Value("${rag.chunk.size:500}")
    private int chunkSize;

    /** 重叠比例（相对 chunkSize），默认 10% */
    @Value("${rag.chunk.overlap-ratio:0.1}")
    private double chunkOverlapRatio;

    @Transactional
    public DocumentResponse upload(String knowledgeBaseId, MultipartFile file) {
        // 校验知识库归属
        kbService.getMine(knowledgeBaseId);

        String fileName = file.getOriginalFilename();
        DocumentEntity doc = new DocumentEntity();
        doc.setKnowledgeBaseId(knowledgeBaseId);
        doc.setFileName(fileName == null ? "unknown.pdf" : fileName);
        doc.setStatus(0);
        doc = documentRepository.save(doc);

        try {
            // 1. 解析 PDF
            String text = pdfParseService.extractText(file);

            // 2. 按语义切分（句子边界 + 10% 重叠）
            List<String> chunks = textSplitter.split(text, chunkSize, chunkOverlapRatio);
            if (chunks.isEmpty()) {
                throw BizException.badRequest("PDF 切分后无有效文本块");
            }

            // 3. 批量 Embedding
            List<float[]> embeddings = embeddingClient.embedBatch(
                    chunks,
                    AuthContext.require().userId(),
                    AuthContext.require().username()
            );
            if (embeddings.size() != chunks.size()) {
                throw BizException.badRequest("Embedding 结果数量与文本块数量不一致");
            }

            // 4. 保存 chunks 到向量存储
            final String documentId = doc.getId();
            List<ChunkData> chunkDataList = IntStream.range(0, chunks.size())
                    .mapToObj(i -> new ChunkData(
                            null,
                            documentId,
                            knowledgeBaseId,
                            i,
                            chunks.get(i),
                            embeddings.get(i)
                    ))
                    .collect(Collectors.toList());
            vectorStore.saveChunks(doc.getId(), knowledgeBaseId, chunkDataList);

            doc.setStatus(1);
            doc.setPageCount(1); // PDFBox 未直接分页计数，后续可细化
            doc = documentRepository.save(doc);

            log.info("知识库 {} 上传文档 {}，生成 {} 个 chunks", knowledgeBaseId, doc.getFileName(), chunkDataList.size());
            return toResponse(doc);
        } catch (Exception e) {
            doc.setStatus(-1);
            doc.setErrorMessage(e.getMessage());
            documentRepository.save(doc);
            throw e;
        }
    }

    public List<DocumentResponse> list(String knowledgeBaseId) {
        kbService.getMine(knowledgeBaseId);
        return documentRepository.findByKnowledgeBaseIdOrderByCreatedAtDesc(knowledgeBaseId)
                .stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public void delete(String knowledgeBaseId, String documentId) {
        kbService.getMine(knowledgeBaseId);
        DocumentEntity doc = documentRepository.findById(documentId)
                .orElseThrow(() -> BizException.notFound("文档不存在"));
        if (!doc.getKnowledgeBaseId().equals(knowledgeBaseId)) {
            throw BizException.badRequest("文档不属于该知识库");
        }
        vectorStore.deleteByDocumentId(documentId);
        documentRepository.delete(doc);
    }

    private DocumentResponse toResponse(DocumentEntity doc) {
        return new DocumentResponse(
                doc.getId(),
                doc.getKnowledgeBaseId(),
                doc.getFileName(),
                doc.getStatus(),
                doc.getPageCount(),
                doc.getErrorMessage(),
                doc.getCreatedAt(),
                doc.getUpdatedAt()
        );
    }
}
