package com.v3agent.gateway.repo;

import com.v3agent.gateway.auth.RequirePermission;
import com.v3agent.gateway.common.ApiResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 仓库(渠道)管理 —— 模型提供方接入点的增删改查 */
@RestController
@RequestMapping("/api/channels")
@RequiredArgsConstructor
public class ChannelController {

    private final ChannelService channelService;

    /** 登录用户可读(模型调用调试台需要渠道/模型下拉) */
    @GetMapping
    @RequirePermission(RequirePermission.AUTH)
    public ApiResponse<List<ChannelEntity>> list() {
        return ApiResponse.ok(channelService.listAll(), "查询渠道列表成功");
    }

    @PostMapping
    @RequirePermission(RequirePermission.SUPER)
    public ApiResponse<ChannelEntity> create(@Valid @RequestBody ChannelRequest req) {
        return ApiResponse.ok(channelService.create(req), "新增渠道成功");
    }

    @PutMapping("/{id}")
    @RequirePermission(RequirePermission.SUPER)
    public ApiResponse<ChannelEntity> update(@PathVariable String id,
                                             @Valid @RequestBody ChannelRequest req) {
        return ApiResponse.ok(channelService.update(id, req), "修改渠道成功");
    }

    public record StatusRequest(Integer status) {}

    public record FetchModelsRequest(String baseUrl, String apiKey, String authType) {}

    /** 真实调用上游 GET {baseUrl}/models 拉取模型列表(新增/编辑渠道时一键回填,
     * 渠道卡片上的「获取模型」按钮也走这里) */
    @PostMapping("/fetch-models")
    @RequirePermission(RequirePermission.SUPER)
    public ApiResponse<List<String>> fetchModels(@RequestBody FetchModelsRequest req) {
        if (req.baseUrl() == null || req.baseUrl().isBlank()) {
            throw com.v3agent.gateway.common.BizException.badRequest("接口地址不能为空");
        }
        return ApiResponse.ok(
                channelService.fetchModels(req.baseUrl(), req.apiKey() == null ? "" : req.apiKey(), req.authType()),
                "获取模型列表成功");
    }

    @PutMapping("/{id}/status")
    @RequirePermission(RequirePermission.SUPER)
    public ApiResponse<ChannelEntity> changeStatus(@PathVariable String id,
                                                   @RequestBody StatusRequest req) {
        return ApiResponse.ok(channelService.changeStatus(id, req.status() == null ? 1 : req.status()), "修改渠道状态成功");
    }

    @DeleteMapping("/{id}")
    @RequirePermission(RequirePermission.SUPER)
    public ApiResponse<Void> delete(@PathVariable String id) {
        channelService.delete(id);
        return ApiResponse.ok("删除渠道成功");
    }
}
