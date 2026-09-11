package com.v3agent.gateway.auth;

import com.v3agent.gateway.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 管理端当前用户接口。
 * 登录/注册已收敛到 NestJS 业务网关(唯一用户权限权威),
 * 本网关只校验 NestJS 签发的 JWT,不再签发。
 * 无状态 JWT,登出由前端清除 token,无需服务端接口。
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @GetMapping("/me")
    @RequirePermission(RequirePermission.AUTH)
    public ApiResponse<AuthService.SafeUser> me() {
        return ApiResponse.ok(authService.me(AuthContext.require().userId()), "查询当前用户成功");
    }
}
