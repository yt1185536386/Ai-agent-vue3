package com.v3agent.gateway.user;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户实体,字段对齐 NestJS 网关 users 表。
 * 权限语义: isSuperAdmin 超级管理员全通;其余用户按「职级批量绑定 +
 * 个人逐项覆盖」解析有效权限码(job_level_permissions / user_permissions)。
 */
@Data
@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(length = 36)
    private String id;

    /** 登录用户名(唯一) */
    @Column(unique = true, nullable = false, length = 64)
    private String username;

    /** bcrypt 密码哈希(不随接口返回) */
    @JsonIgnore
    @Column(nullable = false)
    private String passwordHash;

    @Column(unique = true, length = 120)
    private String email;

    @Column(length = 100)
    private String displayName;

    @Column(length = 255)
    private String avatar;

    /** 超级管理员标记: 拥有全部权限点 */
    @Column(nullable = false)
    private Boolean isSuperAdmin = false;

    /** 职级 id(job_levels.id,权限绑定维度之一) */
    private Integer jobLevelId;

    /** 所属部门 id(departments.id,每个用户只属于一个部门) */
    private Integer departmentId;

    /** 部门内职位: MANAGER 经理 / DEPUTY 副经理 / LEADER 组长 / MEMBER 组员 */
    @Column(nullable = false, length = 20)
    private String deptPosition = "MEMBER";

    /** 状态: 1 启用 / 0 禁用 */
    @Column(nullable = false)
    private Integer status = 1;

    private LocalDateTime lastLoginAt;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = createdAt;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
