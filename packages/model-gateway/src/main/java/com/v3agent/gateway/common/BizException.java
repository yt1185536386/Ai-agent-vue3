package com.v3agent.gateway.common;

import lombok.Getter;

/** 业务异常,由 GlobalExceptionHandler 统一转为 ApiResponse */
@Getter
public class BizException extends RuntimeException {

    private final int errCode;
    private final int httpStatus;

    public BizException(int httpStatus, int errCode, String message) {
        super(message);
        this.httpStatus = httpStatus;
        this.errCode = errCode;
    }

    public static BizException badRequest(String message) {
        return new BizException(400, 400, message);
    }

    public static BizException unauthorized(String message) {
        return new BizException(401, 401, message);
    }

    public static BizException notFound(String message) {
        return new BizException(404, 404, message);
    }

    /** 触发限流 */
    public static BizException rateLimited(String message) {
        return new BizException(429, 429, message);
    }

    /** 触发熔断 */
    public static BizException circuitOpen(String message) {
        return new BizException(503, 503, message);
    }
}
