package com.v3agent.gateway.perm;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;

/** 权限点字典(只读,对齐 NestJS permissions 表) */
@Data
@Entity
@Table(name = "permissions")
public class PermissionEntity {

    @Id
    private Integer id;

    /** 权限码,如 dept:member / log:view / policy:manage */
    @Column(unique = true, nullable = false, length = 64)
    private String code;

    @Column(length = 32)
    private String module;

    @Column(length = 16)
    private String action;

    @Column(length = 64)
    private String name;
}
