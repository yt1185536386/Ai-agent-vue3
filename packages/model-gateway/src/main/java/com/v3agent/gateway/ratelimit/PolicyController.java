package com.v3agent.gateway.ratelimit;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 限流/熔断策略管理 */
@RestController
@RequestMapping("/api/policies")
@RequirePermission("policy:manage")
@RequiredArgsConstructor
public class PolicyController {

    private final PolicyService policyService;
    private final CircuitBreaker circuitBreaker;

    @GetMapping
    public ApiResponse<List<PolicyEntity>> list(@RequestParam(required = false) String type) {
        List<PolicyEntity> all = policyService.listAll();
        if (type == null) {
            return ApiResponse.ok(all, "查询策略列表成功");
        }
        return ApiResponse.ok(all.stream().filter(p -> type.equals(p.getType())).toList(), "查询策略列表成功");
    }

    @PostMapping
    public ApiResponse<PolicyEntity> create(@RequestBody PolicyEntity policy) {
        policy.setId(null);
        return ApiResponse.ok(policyService.save(policy), "新增策略成功");
    }

    @PutMapping("/{id}")
    public ApiResponse<PolicyEntity> update(@PathVariable String id, @RequestBody PolicyEntity policy) {
        policy.setId(id);
        return ApiResponse.ok(policyService.save(policy), "修改策略成功");
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable String id) {
        policyService.delete(id);
        return ApiResponse.ok("删除策略成功");
    }

    /** 查询某策略在某渠道上的熔断器实时状态 */
    @GetMapping("/{id}/circuit-state")
    public ApiResponse<String> circuitState(@PathVariable String id,
                                            @RequestParam(required = false) String channelId) {
        PolicyEntity policy = policyService.listAll().stream()
                .filter(p -> p.getId().equals(id)).findFirst()
                .orElse(null);
        if (policy == null) {
            return ApiResponse.error(404, "策略不存在");
        }
        return ApiResponse.ok(circuitBreaker.stateOf(policy, channelId), "查询熔断状态成功");
    }
}
