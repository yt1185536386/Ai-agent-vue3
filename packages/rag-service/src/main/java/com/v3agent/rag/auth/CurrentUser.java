package com.v3agent.rag.auth;

/** 当前登录用户，由 AuthInterceptor 写入 AuthContext */
public record CurrentUser(String userId, String username) {
}
