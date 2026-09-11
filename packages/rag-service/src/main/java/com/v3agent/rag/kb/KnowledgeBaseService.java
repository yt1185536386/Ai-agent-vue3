package com.v3agent.rag.kb;

import com.v3agent.rag.auth.AuthContext;
import com.v3agent.rag.common.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class KnowledgeBaseService {

    private final KnowledgeBaseRepository kbRepository;

    @Transactional
    public KnowledgeBaseEntity create(String name, String description) {
        KnowledgeBaseEntity kb = new KnowledgeBaseEntity();
        kb.setName(name.trim());
        kb.setDescription(description == null ? null : description.trim());
        kb.setOwnerUserId(AuthContext.require().userId());
        return kbRepository.save(kb);
    }

    public List<KnowledgeBaseEntity> listMine() {
        return kbRepository.findByOwnerUserIdOrderByCreatedAtDesc(AuthContext.require().userId());
    }

    public KnowledgeBaseEntity getMine(String id) {
        KnowledgeBaseEntity kb = kbRepository.findById(id)
                .orElseThrow(() -> BizException.notFound("知识库不存在"));
        if (!kb.getOwnerUserId().equals(AuthContext.require().userId())) {
            throw BizException.badRequest("无权限访问该知识库");
        }
        return kb;
    }

    @Transactional
    public void delete(String id) {
        KnowledgeBaseEntity kb = getMine(id);
        kbRepository.delete(kb);
    }
}
