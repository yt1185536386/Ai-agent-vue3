package com.v3agent.rag.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

import java.util.List;

/**
 * 统一响应体，与 model-gateway 保持一致：
 * errCode = "0" 表示成功，其余为业务错误码。
 */
@Data
public class ApiResponse<T> {

    public static final String SUCCESS = "0";

    private String errCode;
    private String errMsg;
    private T data;

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private Long total;

    public static <T> ApiResponse<T> ok(T data, String errMsg) {
        ApiResponse<T> r = new ApiResponse<>();
        r.errCode = SUCCESS;
        r.errMsg = errMsg;
        r.data = data;
        return r;
    }

    public static ApiResponse<Void> ok(String errMsg) {
        return ok(null, errMsg);
    }

    public static <T> ApiResponse<List<T>> page(List<T> list, long total, String errMsg) {
        ApiResponse<List<T>> r = new ApiResponse<>();
        r.errCode = SUCCESS;
        r.errMsg = errMsg;
        r.data = list;
        r.total = total;
        return r;
    }

    public static <T> ApiResponse<T> error(String errCode, String errMsg) {
        ApiResponse<T> r = new ApiResponse<>();
        r.errCode = errCode;
        r.errMsg = errMsg;
        return r;
    }

    public static <T> ApiResponse<T> error(int errCode, String errMsg) {
        return error(String.valueOf(errCode), errMsg);
    }
}
