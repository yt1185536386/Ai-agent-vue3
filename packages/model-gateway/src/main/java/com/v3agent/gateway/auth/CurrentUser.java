package com.v3agent.gateway.auth;

import java.util.Set;

/** 当前登录用户(写入 AuthContext);perms 为已解析的有效权限码集合 */
public record CurrentUser(String userId, String username, boolean isSuperAdmin, Set<String> perms) {
}
