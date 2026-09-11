package com.v3agent.gateway.perm;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface JobLevelPermRepository extends JpaRepository<JobLevelPermEntity, Integer> {

    List<JobLevelPermEntity> findByJobLevelId(Integer jobLevelId);
}
