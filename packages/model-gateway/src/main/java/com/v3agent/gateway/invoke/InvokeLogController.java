package com.v3agent.gateway.invoke;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/** 调用日志查询 */
@RestController
@RequestMapping("/api/logs")
@RequirePermission("log:view")
@RequiredArgsConstructor
public class InvokeLogController {

    private final InvokeLogRepository logRepository;

    @GetMapping
    public ApiResponse<List<InvokeLogEntity>> page(
            @RequestParam(required = false) String username,
            @RequestParam(required = false) String model,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        Specification<InvokeLogEntity> spec = (root, q, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (username != null && !username.isBlank()) {
                ps.add(cb.like(root.get("username"), "%" + username + "%"));
            }
            if (model != null && !model.isBlank()) {
                ps.add(cb.like(root.get("model"), "%" + model + "%"));
            }
            if (status != null) {
                ps.add(cb.equal(root.get("status"), status));
            }
            if (start != null) {
                ps.add(cb.greaterThanOrEqualTo(root.get("createdAt"), start));
            }
            if (end != null) {
                ps.add(cb.lessThanOrEqualTo(root.get("createdAt"), end));
            }
            return cb.and(ps.toArray(new Predicate[0]));
        };
        Page<InvokeLogEntity> result = logRepository.findAll(spec,
                PageRequest.of(Math.max(page - 1, 0), Math.min(size, 200),
                        Sort.by(Sort.Direction.DESC, "createdAt")));
        return ApiResponse.page(result.getContent(), result.getTotalElements(), "分页查询调用日志成功");
    }
}
