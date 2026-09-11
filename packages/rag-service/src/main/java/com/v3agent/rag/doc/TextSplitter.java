package com.v3agent.rag.doc;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 语义感知的文本切分器。
 * <p>
 * 按句子边界（。！？!?.;: 或换行）把文本切成句子，再贪心地把句子装入 chunk：
 * 装入下一句会超过 maxSize 时就封块，保证 chunk 不会在句子中间截断。
 * 相邻 chunk 之间携带上一个 chunk 尾部约 maxSize * overlapRatio 的重叠内容
 * （优先取完整句子，取不到时退化为按字符截尾），避免跨块语义断裂。
 * 单句超过 maxSize 时退化为带重叠的滑动窗口硬切。
 */
@Component
public class TextSplitter {

    /** 句子单元：到句末标点或换行为止，附带其后的空白（保留段落换行结构） */
    private static final Pattern SENTENCE = Pattern.compile("[^。！？!?;:：\\n]+[。！？!?;:：]?\\s*");

    /**
     * @param text         待切分文本
     * @param maxSize      chunk 最大字符数
     * @param overlapRatio 重叠比例，相对 maxSize，如 0.1 表示 10%
     */
    public List<String> split(String text, int maxSize, double overlapRatio) {
        List<String> chunks = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return chunks;
        }
        if (maxSize <= 0) {
            throw new IllegalArgumentException("maxSize must be positive");
        }
        if (overlapRatio < 0 || overlapRatio >= 1) {
            throw new IllegalArgumentException("overlapRatio must be in [0, 1)");
        }
        int overlapChars = (int) (maxSize * overlapRatio);

        StringBuilder current = new StringBuilder();
        Matcher m = SENTENCE.matcher(text);
        while (m.find()) {
            String sentence = m.group();
            if (sentence.isBlank()) {
                continue;
            }
            if (sentence.trim().length() > maxSize) {
                // 超长单句（无标点长段）：先封当前块，再滑动窗口硬切
                flush(chunks, current);
                hardCut(sentence.trim(), maxSize, overlapChars, chunks);
                continue;
            }
            if (current.length() + sentence.length() > maxSize && current.length() > 0) {
                String overlap = tailOverlap(current.toString(), overlapChars);
                flush(chunks, current);
                current.append(overlap);
            }
            current.append(sentence);
        }
        flush(chunks, current);
        return chunks;
    }

    private void flush(List<String> chunks, StringBuilder current) {
        if (current.length() > 0 && !current.toString().isBlank()) {
            chunks.add(current.toString().trim());
        }
        current.setLength(0);
    }

    /**
     * 取已封块文本的尾部作为下一块的重叠前缀。
     * 优先取尾部完整句子（总长按 overlapChars 控制），第一句都装不下时按字符截尾。
     */
    private String tailOverlap(String chunk, int overlapChars) {
        if (overlapChars <= 0) {
            return "";
        }
        List<String> tailSentences = new ArrayList<>();
        int total = 0;
        Matcher m = SENTENCE.matcher(chunk);
        List<String> sentences = new ArrayList<>();
        while (m.find()) {
            if (!m.group().isBlank()) {
                sentences.add(m.group());
            }
        }
        for (int i = sentences.size() - 1; i >= 0; i--) {
            String s = sentences.get(i);
            if (total + s.length() > overlapChars && !tailSentences.isEmpty()) {
                break;
            }
            tailSentences.add(0, s);
            total += s.length();
            if (total >= overlapChars) {
                break;
            }
        }
        if (!tailSentences.isEmpty() && tailSentences.size() < sentences.size()) {
            return String.join("", tailSentences);
        }
        // 整块就是一句话：按字符截尾
        return chunk.length() <= overlapChars ? "" : chunk.substring(chunk.length() - overlapChars);
    }

    /** 无标点超长文本的兜底：固定窗口 + 字符重叠硬切 */
    private void hardCut(String text, int maxSize, int overlapChars, List<String> chunks) {
        int step = Math.max(1, maxSize - overlapChars);
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + maxSize, text.length());
            chunks.add(text.substring(start, end).trim());
            if (end == text.length()) {
                break;
            }
            start += step;
        }
    }
}
