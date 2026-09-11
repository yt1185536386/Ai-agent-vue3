package com.v3agent.gateway.user;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import com.v3agent.gateway.common.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 用户查询(只读)。
 * 用户的新增/修改/删除统一在 NestJS 业务网关(规则引擎唯一实现),
 * 本网关不再提供写接口,避免绕过业务规则直写共享 users 表。
 */
@RestController
@RequestMapping("/api/users")
@RequirePermission(RequirePermission.SUPER)
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping
    public ApiResponse<List<UserEntity>> page(@RequestParam(required = false) String keyword,
                                              @RequestParam(required = false) Integer status,
                                              @RequestParam(defaultValue = "1") int page,
                                              @RequestParam(defaultValue = "10") int size) {
        PageResult<UserEntity> result = userService.page(keyword, status, page, size);
        return ApiResponse.page(result.getList(), result.getTotal(), "分页查询用户成功");
    }
}
