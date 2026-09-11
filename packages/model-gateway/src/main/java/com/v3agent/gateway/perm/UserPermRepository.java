package com.v3agent.gateway.perm;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface UserPermRepository extends JpaRepository<UserPermEntity, Integer> {

    List<UserPermEntity> findByUserId(String userId);
}
