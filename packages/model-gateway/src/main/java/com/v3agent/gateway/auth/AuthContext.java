package com.v3agent.gateway.auth;

import com.v3agent.gateway.common.BizException;

/** 请求级登录用户上下文,由 AuthInterceptor 写入/清理 */
public final class AuthContext {

    private static final ThreadLocal<CurrentUser> HOLDER = new ThreadLocal<>();

    private AuthContext() {}

    public static void set(CurrentUser user) {
        HOLDER.set(user);
    }

    public static CurrentUser get() {
        return HOLDER.get();
    }

    /** 未登录直接 401,等价于 NestJS JwtAuthGuard */
    public static CurrentUser require() {
        CurrentUser user = HOLDER.get();
        if (user == null) {
            throw BizException.unauthorized("未登录或登录已过期");
        }
        return user;
    }

    public static void clear() {
        HOLDER.remove();
    }
}
