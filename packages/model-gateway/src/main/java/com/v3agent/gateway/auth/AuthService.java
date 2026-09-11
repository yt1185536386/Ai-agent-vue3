package com.v3agent.gateway.auth;

import com.v3agent.gateway.user.UserEntity;
import com.v3agent.gateway.user.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserService userService;

    /** 脱敏用户信息 */
    public record SafeUser(String id, String username, String email, String displayName,
                           String avatar, Boolean isSuperAdmin, Integer jobLevelId,
                           Integer departmentId, String deptPosition, Integer status,
                           java.time.LocalDateTime lastLoginAt) {
        public static SafeUser of(UserEntity u) {
            return new SafeUser(u.getId(), u.getUsername(), u.getEmail(), u.getDisplayName(),
                    u.getAvatar(), u.getIsSuperAdmin(), u.getJobLevelId(), u.getDepartmentId(),
                    u.getDeptPosition(), u.getStatus(), u.getLastLoginAt());
        }
    }

    public SafeUser me(String userId) {
        return SafeUser.of(userService.findById(userId));
    }
}
