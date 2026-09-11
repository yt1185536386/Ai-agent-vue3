package com.v3agent.rag.user;

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
 * 用户实体（只读），字段与 model-gateway / NestJS 网关 users 表对齐。
 * RAG 服务只用于回库校验 JWT 对应用户是否存在且未被禁用。
 */
@Data
@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(length = 36)
    private String id;

    @Column(unique = true, nullable = false, length = 64)
    private String username;

    @Column(unique = true, length = 120)
    private String email;

    @Column(length = 100)
    private String displayName;

    @Column(length = 255)
    private String avatar;

    @Column(nullable = false)
    private Boolean isSuperAdmin = false;

    private Integer jobLevelId;

    private Integer departmentId;

    @Column(nullable = false, length = 20)
    private String deptPosition = "MEMBER";

    /** 状态：1 启用 / 0 禁用 */
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
