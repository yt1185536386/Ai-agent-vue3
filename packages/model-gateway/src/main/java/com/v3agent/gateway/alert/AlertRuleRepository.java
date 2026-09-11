package com.v3agent.gateway.alert;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AlertRuleRepository extends JpaRepository<AlertRuleEntity, String> {

    List<AlertRuleEntity> findByEnabled(Integer enabled);
}
