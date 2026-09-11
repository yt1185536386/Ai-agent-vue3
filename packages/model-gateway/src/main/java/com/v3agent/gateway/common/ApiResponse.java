package com.v3agent.gateway.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

import java.util.List;

/**
 * 统一响应体,与前端约定(见前端 src/api/api.json):
 * <pre>
 *   普通接口: { "errCode": "0", "errMsg": "请求成功", "data": {...} }
 *   分页接口: { "errCode": "0", "errMsg": "分页查询xx成功", "data": [...], "total": 1 }
 * </pre>
 * errCode = "0" 表示成功,其余为业务错误码。
 */
@Data
public class ApiResponse<T> {

    public static final String SUCCESS = "0";

    private String errCode;
    private String errMsg;
    private T data;

    /** 仅分页接口返回总记录数,非分页不序列化 */
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

    /** 分页接口: data 为当前页列表, total 为总记录数 */
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

    /** 便于与 HTTP 状态码对齐的重载 */
    public static <T> ApiResponse<T> error(int errCode, String errMsg) {
        return error(String.valueOf(errCode), errMsg);
    }
}
