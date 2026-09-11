package com.v3agent.gateway.alert;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface AlertRecordRepository extends JpaRepository<AlertRecordEntity, String>,
        JpaSpecificationExecutor<AlertRecordEntity> {

    long countByReadFlag(Integer readFlag);

    /** 静默期查重: 同规则同对象在 cooldown 内已有记录则跳过 */
    boolean existsByRuleIdAndTargetKeyAndCreatedAtAfter(String ruleId, String targetKey, LocalDateTime after);

    /** 查某规则在某对象上的活跃告警,指标回落时置 RESOLVED */
    List<AlertRecordEntity> findByStatusAndRuleIdAndTargetKey(String status, String ruleId, String targetKey);

    /** 查某指标类型的全部活跃告警(熔断恢复检测用) */
    List<AlertRecordEntity> findByStatusAndMetric(String status, String metric);

    @Modifying
    @Query("update AlertRecordEntity r set r.readFlag = 1 where r.readFlag = 0")
    int markAllRead();

    /** 定期清理: 只保留最近 N 天的记录,防止流水表无限膨胀 */
    @Modifying
    @Query("delete from AlertRecordEntity r where r.createdAt < :before")
    int deleteOlderThan(@Param("before") LocalDateTime before);
}
