package com.v3agent.gateway.invoke;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface InvokeLogRepository extends JpaRepository<InvokeLogEntity, String>, JpaSpecificationExecutor<InvokeLogEntity> {

    interface AggregateRow {
        String getGroupKey();
        long getCalls();
        long getTokens();
        long getErrors();
    }

    /** 按用户名聚合 */
    @Query("select l.username as groupKey, count(l) as calls, sum(l.totalTokens) as tokens, " +
            "sum(case when l.status = 0 then 1 else 0 end) as errors " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "and (:username is null or l.username like concat('%', :username, '%')) " +
            "group by l.username order by calls desc")
    List<AggregateRow> aggregateByUser(@Param("start") LocalDateTime start,
                                       @Param("end") LocalDateTime end,
                                       @Param("username") String username);

    /** 按模型聚合 */
    @Query("select l.model as groupKey, count(l) as calls, sum(l.totalTokens) as tokens, " +
            "sum(case when l.status = 0 then 1 else 0 end) as errors " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "and (:username is null or l.username like concat('%', :username, '%')) " +
            "group by l.model order by calls desc")
    List<AggregateRow> aggregateByModel(@Param("start") LocalDateTime start,
                                        @Param("end") LocalDateTime end,
                                        @Param("username") String username);

    /** 按渠道聚合 */
    @Query("select l.channelName as groupKey, count(l) as calls, sum(l.totalTokens) as tokens, " +
            "sum(case when l.status = 0 then 1 else 0 end) as errors " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "and (:username is null or l.username like concat('%', :username, '%')) " +
            "group by l.channelName order by calls desc")
    List<AggregateRow> aggregateByChannel(@Param("start") LocalDateTime start,
                                          @Param("end") LocalDateTime end,
                                          @Param("username") String username);

    /** 趋势明细(由 StatsController 在 Java 侧按小时分桶,避免依赖数据库方言函数) */
    @Query("select l.createdAt as ts, l.totalTokens as tokens, l.status as status " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "and (:username is null or l.username like concat('%', :username, '%'))")
    List<TrendPoint> findForTrend(@Param("start") LocalDateTime start,
                                  @Param("end") LocalDateTime end,
                                  @Param("username") String username);

    interface TrendPoint {
        LocalDateTime getTs();
        long getTokens();
        int getStatus();
    }

    /** 告警评估用: 时间窗内按渠道聚合调用量/错误数/平均时延 */
    @Query("select l.channelId as channelId, l.channelName as channelName, count(l) as calls, " +
            "sum(case when l.status = 0 then 1 else 0 end) as errors, avg(l.durationMs) as avgDuration " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "group by l.channelId, l.channelName")
    List<ChannelWindowStat> windowStatByChannel(@Param("start") LocalDateTime start,
                                                @Param("end") LocalDateTime end);

    interface ChannelWindowStat {
        String getChannelId();
        String getChannelName();
        long getCalls();
        long getErrors();
        Double getAvgDuration();
    }

    /** 用户 × 模型 交叉分布(看板堆叠柱状图) */
    @Query("select l.username as groupKey, l.model as model, count(l) as calls, sum(l.totalTokens) as tokens " +
            "from InvokeLogEntity l where l.createdAt between :start and :end " +
            "and (:username is null or l.username like concat('%', :username, '%')) " +
            "group by l.username, l.model")
    List<UserModelRow> aggregateUserModel(@Param("start") LocalDateTime start,
                                          @Param("end") LocalDateTime end,
                                          @Param("username") String username);

    interface UserModelRow {
        String getGroupKey();
        String getModel();
        long getCalls();
        long getTokens();
    }
}
