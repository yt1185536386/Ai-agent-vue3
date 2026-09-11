package com.v3agent.gateway.perm;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;

/** 个人权限绑定(只读,对齐 NestJS user_permissions 表): 逐权限点覆盖职级绑定 */
@Data
@Entity
@Table(name = "user_permissions")
public class UserPermEntity {

    @Id
    private Integer id;

    @Column(nullable = false, length = 36)
    private String userId;

    @Column(nullable = false)
    private Integer permissionId;

    /** true 授予 / false 拒绝 */
    @Column(nullable = false)
    private Boolean allowed;
}
