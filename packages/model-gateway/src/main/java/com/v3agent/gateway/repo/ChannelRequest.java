package com.v3agent.gateway.repo;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

public record ChannelRequest(
        @NotBlank(message = "渠道名称不能为空") String name,
        String channelKey,
        @NotBlank(message = "提供方类型不能为空") String provider,
        String upstreamFormat,
        String authType,
        @NotBlank(message = "接口地址不能为空") String baseUrl,
        @NotBlank(message = "API Key 不能为空") String apiKey,
        @NotEmpty(message = "至少配置一个模型") List<String> models,
        Boolean enableSearch,
        Boolean supportsTools,
        Integer priority,
        Integer status,
        String remark
) {}
