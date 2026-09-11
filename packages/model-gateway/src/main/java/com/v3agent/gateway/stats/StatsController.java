package com.v3agent.gateway.stats;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import com.v3agent.gateway.invoke.InvokeLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** 数据概览: 数据看板一次取全(统计卡片 + 各维度聚合 + 趋势 + 用户×模型分布) */
@RestController
@RequestMapping("/api/stats")
@RequirePermission(RequirePermission.SUPER)
@RequiredArgsConstructor
public class StatsController {

    private final InvokeLogRepository logRepository;

    public record Summary(long totalCalls, long totalTokens,
                          double callsPerMinute, double tokensPerMinute,
                          double errorRate, long totalErrors) {}

    public record AggregateRow(String groupKey, long calls, long tokens, long errors) {}

    public record UserModelRow(String username, String model, long calls, long tokens) {}

    public record Overview(Summary summary,
                           List<AggregateRow> byUser,
                           List<AggregateRow> byModel,
                           List<AggregateRow> byChannel,
                           List<AggregateRow> trend,
                           List<UserModelRow> userModel) {}

    @GetMapping("/overview")
    public ApiResponse<Overview> overview(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(required = false) String username) {

        List<InvokeLogRepository.AggregateRow> byUser = logRepository.aggregateByUser(start, end, username);
        List<InvokeLogRepository.AggregateRow> byModel = logRepository.aggregateByModel(start, end, username);
        List<InvokeLogRepository.AggregateRow> byChannel = logRepository.aggregateByChannel(start, end, username);
        List<InvokeLogRepository.UserModelRow> userModel = logRepository.aggregateUserModel(start, end, username);

        // 按小时分桶(调用趋势),TreeMap 保证时间有序
        Map<String, long[]> buckets = new TreeMap<>();
        DateTimeFormatter hourFmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:00");
        for (InvokeLogRepository.TrendPoint p : logRepository.findForTrend(start, end, username)) {
            long[] agg = buckets.computeIfAbsent(p.getTs().format(hourFmt), k -> new long[3]);
            agg[0]++;                    // calls
            agg[1] += p.getTokens();     // tokens
            if (p.getStatus() == 0) {
                agg[2]++;                // errors
            }
        }
        List<AggregateRow> trend = buckets.entrySet().stream()
                .map(e -> new AggregateRow(e.getKey(), e.getValue()[0], e.getValue()[1], e.getValue()[2]))
                .toList();

        long totalCalls = byUser.stream().mapToLong(InvokeLogRepository.AggregateRow::getCalls).sum();
        long totalTokens = byUser.stream().mapToLong(r -> r.getTokens() == 0 ? 0 : r.getTokens()).sum();
        long totalErrors = byUser.stream().mapToLong(InvokeLogRepository.AggregateRow::getErrors).sum();
        double minutes = Math.max(Duration.between(start, end).toMinutes(), 1);
        Summary summary = new Summary(
                totalCalls,
                totalTokens,
                totalCalls / minutes,
                totalTokens / minutes,
                totalCalls == 0 ? 0 : totalErrors * 100.0 / totalCalls,
                totalErrors);

        return ApiResponse.ok(new Overview(
                summary,
                byUser.stream().map(StatsController::toRow).toList(),
                byModel.stream().map(StatsController::toRow).toList(),
                byChannel.stream().map(StatsController::toRow).toList(),
                trend,
                userModel.stream().map(r -> new UserModelRow(r.getGroupKey(), r.getModel(),
                        r.getCalls(), r.getTokens())).toList()), "查询数据概览成功");
    }

    private static AggregateRow toRow(InvokeLogRepository.AggregateRow r) {
        return new AggregateRow(r.getGroupKey(), r.getCalls(), r.getTokens(), r.getErrors());
    }

    /** 简单健康/实时概览(卡片右侧小指标用) */
    @GetMapping("/realtime")
    public ApiResponse<Map<String, Object>> realtime() {
        LocalDateTime now = LocalDateTime.now();
        List<InvokeLogRepository.AggregateRow> lastMinute =
                logRepository.aggregateByUser(now.minusMinutes(1), now, null);
        long calls = lastMinute.stream().mapToLong(InvokeLogRepository.AggregateRow::getCalls).sum();
        long tokens = lastMinute.stream().mapToLong(InvokeLogRepository.AggregateRow::getTokens).sum();
        long errors = lastMinute.stream().mapToLong(InvokeLogRepository.AggregateRow::getErrors).sum();
        return ApiResponse.ok(Map.of(
                "callsLastMinute", calls,
                "tokensLastMinute", tokens,
                "errorsLastMinute", errors), "查询实时指标成功");
    }
}
