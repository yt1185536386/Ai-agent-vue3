package com.v3agent.gateway.user;

import com.v3agent.gateway.common.BizException;
import com.v3agent.gateway.common.PageResult;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;

/**
 * 用户查询(只读)。用户写操作已收敛到 NestJS 业务网关,
 * 本类只保留管理端列表/详情查询。
 */
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;

    public UserEntity findById(String id) {
        return userRepository.findById(id)
                .orElseThrow(() -> BizException.notFound("用户不存在"));
    }

    public PageResult<UserEntity> page(String keyword, Integer status, int page, int size) {
        Specification<UserEntity> spec = (root, q, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (StringUtils.hasText(keyword)) {
                String like = "%" + keyword + "%";
                ps.add(cb.or(cb.like(root.get("username"), like),
                        cb.like(root.get("displayName"), like),
                        cb.like(root.get("email"), like)));
            }
            if (status != null) {
                ps.add(cb.equal(root.get("status"), status));
            }
            return cb.and(ps.toArray(new Predicate[0]));
        };
        Page<UserEntity> result = userRepository.findAll(spec,
                PageRequest.of(Math.max(page - 1, 0), size, Sort.by(Sort.Direction.DESC, "createdAt")));
        return new PageResult<>(result.getTotalElements(), result.getContent());
    }
}
