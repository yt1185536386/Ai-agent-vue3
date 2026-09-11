package com.v3agent.gateway.ratelimit;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PolicyRepository extends JpaRepository<PolicyEntity, String> {

    List<PolicyEntity> findByEnabledAndType(Integer enabled, String type);
}
