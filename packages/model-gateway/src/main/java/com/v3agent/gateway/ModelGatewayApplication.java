package com.v3agent.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 模型服务网关 —— 系统唯一模型出口:
 * 渠道(仓库)管理 / 限流熔断 / 模型调用计量 / 数据概览。
 * 用户权限权威在 NestJS 业务网关,本服务只校验 NestJS 签发的 JWT(不签发)。
 */
@EnableScheduling
@SpringBootApplication
public class ModelGatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(ModelGatewayApplication.class, args);
    }
}
