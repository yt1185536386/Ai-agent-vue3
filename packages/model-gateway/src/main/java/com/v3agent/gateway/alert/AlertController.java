package com.v3agent.gateway.alert;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;

/** 告警中心: 规则管理 + 触发记录(仅管理端看板展示,v1 不外发通知) */
@RestController
@RequestMapping("/api/alerts")
@RequirePermission(RequirePermission.SUPER)
@RequiredArgsConstructor
public class AlertController {

    private final AlertRuleService ruleService;
    private final AlertRecordRepository recordRepository;

    // ---------- 规则管理 ----------

    @GetMapping("/rules")
    public ApiResponse<List<AlertRuleEntity>> listRules() {
        return ApiResponse.ok(ruleService.listAll(), "查询告警规则成功");
    }

    @PostMapping("/rules")
    public ApiResponse<AlertRuleEntity> createRule(@RequestBody AlertRuleEntity rule) {
        rule.setId(null);
        return ApiResponse.ok(ruleService.save(rule), "新增告警规则成功");
    }

    @PutMapping("/rules/{id}")
    public ApiResponse<AlertRuleEntity> updateRule(@PathVariable String id, @RequestBody AlertRuleEntity rule) {
        rule.setId(id);
        return ApiResponse.ok(ruleService.save(rule), "修改告警规则成功");
    }

    @DeleteMapping("/rules/{id}")
    public ApiResponse<Void> deleteRule(@PathVariable String id) {
        ruleService.delete(id);
        return ApiResponse.ok("删除告警规则成功");
    }

    // ---------- 触发记录 ----------

    @GetMapping("/records")
    public ApiResponse<List<AlertRecordEntity>> pageRecords(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String severity,
            @RequestParam(required = false) Integer readFlag,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        Specification<AlertRecordEntity> spec = (root, q, cb) -> {
            List<Predicate> ps = new ArrayList<>();
            if (status != null && !status.isBlank()) {
                ps.add(cb.equal(root.get("status"), status));
            }
            if (severity != null && !severity.isBlank()) {
                ps.add(cb.equal(root.get("severity"), severity));
            }
            if (readFlag != null) {
                ps.add(cb.equal(root.get("readFlag"), readFlag));
            }
            return cb.and(ps.toArray(new Predicate[0]));
        };
        Page<AlertRecordEntity> result = recordRepository.findAll(spec,
                PageRequest.of(Math.max(page - 1, 0), Math.min(size, 200),
                        Sort.by(Sort.Direction.DESC, "createdAt")));
        return ApiResponse.page(result.getContent(), result.getTotalElements(), "分页查询告警记录成功");
    }

    /** 未读数(看板菜单红点,前端轮询) */
    @GetMapping("/records/unread-count")
    public ApiResponse<Long> unreadCount() {
        return ApiResponse.ok(recordRepository.countByReadFlag(0), "查询未读告警数成功");
    }

    @PutMapping("/records/{id}/read")
    public ApiResponse<Void> markRead(@PathVariable String id) {
        recordRepository.findById(id).ifPresent(r -> {
            r.setReadFlag(1);
            recordRepository.save(r);
        });
        return ApiResponse.ok("已标记已读");
    }

    @Transactional
    @PutMapping("/records/read-all")
    public ApiResponse<Void> markAllRead() {
        recordRepository.markAllRead();
        return ApiResponse.ok("已全部标记已读");
    }
}
