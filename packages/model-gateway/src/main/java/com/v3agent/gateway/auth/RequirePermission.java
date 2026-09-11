package com.v3agent.gateway.auth;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 权限要求注解(等价 NestJS PermissionGuard + @RequirePerm):
 * value 为 permissions 表中的权限码(如 "log:view" / "policy:manage")。
 * 有效权限 = 个人绑定逐项覆盖职级绑定;超级管理员全通。
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
public @interface RequirePermission {

    /** 特殊值: 仅超级管理员 */
    String SUPER = "super";
    /** 特殊值: 只要登录即可 */
    String AUTH = "auth";

    /** 权限码,或特殊值 SUPER / AUTH */
    String value() default AUTH;
}
