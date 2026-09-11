package com.v3agent.rag.doc;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TextSplitterTest {

    private final TextSplitter splitter = new TextSplitter();

    @Test
    void split_emptyText_returnsEmpty() {
        assertTrue(splitter.split("", 500, 0.1).isEmpty());
        assertTrue(splitter.split("   ", 500, 0.1).isEmpty());
        assertTrue(splitter.split(null, 500, 0.1).isEmpty());
    }

    @Test
    void split_respectsSentenceBoundaries() {
        // 20 句 × 30 字 = 600 字,maxSize 200 → 多块,且每块必须由完整句子组成
        String sentence = "这是一段用于测试语义切分的中文句子内容";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 20; i++) {
            sb.append(sentence).append(i % 3 == 0 ? "。" : i % 3 == 1 ? "!" : "?");
        }
        List<String> chunks = splitter.split(sb.toString(), 200, 0.1);

        assertTrue(chunks.size() >= 3, "600 字应按 200 上限切成至少 3 块");
        for (String chunk : chunks) {
            assertTrue(chunk.length() <= 200, "chunk 超长: " + chunk.length());
            assertTrue(chunk.matches(".*[。!?]$"), "chunk 必须以句末标点结尾: " + chunk);
        }
    }

    @Test
    void split_carriesTenPercentOverlap() {
        // maxSize 100,重叠 10% = 10 字;构造每句 30 字、共 12 句的文本
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 12; i++) {
            sb.append(String.format("第%02d句这里是一些填充用的文字内容。", i));
        }
        List<String> chunks = splitter.split(sb.toString(), 100, 0.1);

        assertTrue(chunks.size() > 1);
        // 相邻块之间应有重叠:后一块的开头包含前一块尾部的某个句子片段
        for (int i = 1; i < chunks.size(); i++) {
            String prev = chunks.get(i - 1);
            String cur = chunks.get(i);
            // 前一块最后一个句子(以 。结尾的尾部)
            String lastSentence = prev.substring(prev.lastIndexOf('。', prev.length() - 2) + 1);
            assertTrue(cur.startsWith(lastSentence.substring(0, Math.min(4, lastSentence.length()))),
                    "第 " + i + " 块未携带前块重叠内容");
        }
    }

    @Test
    void split_zeroOverlap_noSharedContent() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            sb.append(String.format("第%02d句这里是一些填充用的文字内容。", i));
        }
        List<String> chunks = splitter.split(sb.toString(), 100, 0.0);
        assertTrue(chunks.size() > 1);
        for (int i = 1; i < chunks.size(); i++) {
            String prevLast = chunks.get(i - 1);
            String lastSentence = prevLast.substring(prevLast.lastIndexOf('。', prevLast.length() - 2) + 1);
            assertTrue(!chunks.get(i).startsWith(lastSentence.substring(0, 4)));
        }
    }

    @Test
    void split_longUnpunctuatedText_fallsBackToHardCut() {
        String text = "字".repeat(1000);
        List<String> chunks = splitter.split(text, 500, 0.1);

        assertEquals(3, chunks.size());
        assertEquals(500, chunks.get(0).length());
        assertTrue(chunks.get(1).length() <= 500);
        assertTrue(chunks.get(2).length() <= 500);
    }

    @Test
    void split_preservesParagraphBreaks() {
        String text = "第一段的第一句话。第一段的第二句话。\n\n第二段的第一句话。第二段的第二句话。";
        List<String> chunks = splitter.split(text, 500, 0.1);
        assertEquals(1, chunks.size());
        assertTrue(chunks.get(0).contains("\n"), "段落换行应保留在 chunk 中");
    }

    @Test
    void split_invalidArgs_throws() {
        assertThrows(IllegalArgumentException.class, () -> splitter.split("abc", 0, 0.1));
        assertThrows(IllegalArgumentException.class, () -> splitter.split("abc", 500, -0.1));
        assertThrows(IllegalArgumentException.class, () -> splitter.split("abc", 500, 1.0));
    }
}
