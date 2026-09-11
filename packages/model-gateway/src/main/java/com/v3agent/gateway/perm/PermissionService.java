package com.v3agent.gateway.perm;

import com.v3agent.gateway.user.UserEntity;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 有效权限解析(与 NestJS UsersService.resolvePermissionCodes 同一规则):
 * 超管 → 全部权限点;其余逐权限点 —— 个人绑定有记录则以 allowed 为准,
 * 无记录则继承职级绑定,职级也未绑定则拒绝。
 */
@Service
@RequiredArgsConstructor
public class PermissionService {

    private final PermissionRepository permissionRepository;
    private final UserPermRepository userPermRepository;
    private final JobLevelPermRepository jobLevelPermRepository;

    public Set<String> resolveCodes(UserEntity user) {
        List<PermissionEntity> points = permissionRepository.findAll();
        if (Boolean.TRUE.equals(user.getIsSuperAdmin())) {
            return points.stream().map(PermissionEntity::getCode).collect(Collectors.toSet());
        }
        Map<Integer, Boolean> overrides = new HashMap<>();
        for (UserPermEntity row : userPermRepository.findByUserId(user.getId())) {
            overrides.put(row.getPermissionId(), row.getAllowed());
        }
        Set<Integer> jobLevelPerms = user.getJobLevelId() == null
                ? Set.of()
                : jobLevelPermRepository.findByJobLevelId(user.getJobLevelId()).stream()
                        .map(JobLevelPermEntity::getPermissionId).collect(Collectors.toSet());
        Set<String> codes = new HashSet<>();
        for (PermissionEntity point : points) {
            Boolean override = overrides.get(point.getId());
            if (override != null) {
                if (override) {
                    codes.add(point.getCode());
                }
            } else if (jobLevelPerms.contains(point.getId())) {
                codes.add(point.getCode());
            }
        }
        return codes;
    }
}
