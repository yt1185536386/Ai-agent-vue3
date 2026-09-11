package com.v3agent.gateway.perm;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;

/** 职级权限绑定(只读,对齐 NestJS job_level_permissions 表) */
@Data
@Entity
@Table(name = "job_level_permissions")
public class JobLevelPermEntity {

    @Id
    private Integer id;

    @Column(nullable = false)
    private Integer jobLevelId;

    @Column(nullable = false)
    private Integer permissionId;
}
