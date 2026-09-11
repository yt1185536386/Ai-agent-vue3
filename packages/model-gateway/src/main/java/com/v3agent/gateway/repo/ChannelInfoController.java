package com.v3agent.gateway.repo;

import com.v3agent.gateway.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 内部渠道信息接口（/v1/**），供内部微服务查询渠道配置。
 * 鉴权走 ServiceKeyInterceptor，需要携带内部服务密钥。
 */
@RestController
@RequestMapping("/v1/channels")
@RequiredArgsConstructor
public class ChannelInfoController {

    private final ChannelService channelService;

    @GetMapping("/{channelKey}")
    public ApiResponse<ChannelInfo> getByKey(@PathVariable String channelKey) {
        ChannelEntity entity = channelService.findEnabledByKey(channelKey);
        ChannelInfo info = new ChannelInfo(
                entity.getId(),
                entity.getName(),
                entity.getChannelKey(),
                entity.getProvider(),
                entity.getBaseUrl(),
                entity.getModels() == null ? List.of() : ChannelService.parseModels(entity.getModels()),
                Boolean.TRUE.equals(entity.getEnableSearch())
        );
        return ApiResponse.ok(info, "查询渠道成功");
    }

    public record ChannelInfo(
            String id,
            String name,
            String channelKey,
            String provider,
            String baseUrl,
            List<String> models,
            boolean enableSearch
    ) {}
}
