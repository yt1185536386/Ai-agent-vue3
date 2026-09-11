package com.v3agent.rag.doc;

import com.v3agent.rag.common.BizException;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

/**
 * 使用 Apache PDFBox 从 PDF 中提取纯文本。
 */
@Service
public class PdfParseService {

    public String extractText(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw BizException.badRequest("PDF 文件不能为空");
        }
        String original = file.getOriginalFilename();
        if (original == null || !original.toLowerCase().endsWith(".pdf")) {
            throw BizException.badRequest("仅支持上传 PDF 文件");
        }
        try (PDDocument document = Loader.loadPDF(file.getBytes())) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            String text = stripper.getText(document);
            if (text == null || text.isBlank()) {
                throw BizException.badRequest("PDF 中未提取到文本内容");
            }
            return normalize(text);
        } catch (IOException e) {
            throw BizException.badRequest("PDF 解析失败: " + e.getMessage());
        }
    }

    /** 规范化：压缩行内空白，但保留段落换行（\n\n），供语义切分识别段落边界 */
    private String normalize(String text) {
        return text
                .replace("\r\n", "\n")
                .replaceAll("[ \\t\\x0B\\f]+", " ")
                .replaceAll(" *\\n *", "\n")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }
}
