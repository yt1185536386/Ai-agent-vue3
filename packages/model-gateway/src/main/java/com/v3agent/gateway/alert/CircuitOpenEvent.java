package com.v3agent.gateway.alert;

import org.springframework.context.ApplicationEvent;

/** 熔断打开事件: CircuitBreaker 在 CLOSED/HALF_OPEN -> OPEN 转换时发布 */
public class CircuitOpenEvent extends ApplicationEvent {

    private final String policyId;
    private final String policyName;
    private final String channelId;
    private final double failureRate;

    public CircuitOpenEvent(Object source, String policyId, String policyName,
                            String channelId, double failureRate) {
        super(source);
        this.policyId = policyId;
        this.policyName = policyName;
        this.channelId = channelId == null ? "" : channelId;
        this.failureRate = failureRate;
    }

    public String getPolicyId() {
        return policyId;
    }

    public String getPolicyName() {
        return policyName;
    }

    public String getChannelId() {
        return channelId;
    }

    public double getFailureRate() {
        return failureRate;
    }
}
