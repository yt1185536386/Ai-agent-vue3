package com.v3agent.gateway.common;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @ExceptionHandler(BizException.class)
    public ResponseEntity<?> handleBiz(BizException e, HttpServletRequest request) {
        if (isOpenAiPath(request)) {
            return ResponseEntity.status(e.getHttpStatus()).body(openAiError(e.getMessage()));
        }
        return ResponseEntity.status(e.getHttpStatus())
                .body(ApiResponse.error(e.getErrCode(), e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(MethodArgumentNotValidException e, HttpServletRequest request) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(FieldError::getDefaultMessage)
                .orElse("参数校验失败");
        if (isOpenAiPath(request)) {
            return ResponseEntity.badRequest().body(openAiError(msg));
        }
        return ResponseEntity.badRequest().body(ApiResponse.error(400, msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleOther(Exception e, HttpServletRequest request) {
        log.error("未处理异常", e);
        if (isOpenAiPath(request)) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(openAiError("服务器内部错误: " + e.getMessage()));
        }
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
    }

    /** /v1/** 面向 OpenAI SDK,错误体必须是 { error: { message } } 结构 */
    private boolean isOpenAiPath(HttpServletRequest request) {
        return request.getRequestURI() != null && request.getRequestURI().startsWith("/v1/");
    }

    private ObjectNode openAiError(String message) {
        ObjectNode error = MAPPER.createObjectNode();
        error.put("message", message);
        error.put("type", "gateway_error");
        error.putNull("param");
        error.putNull("code");
        ObjectNode body = MAPPER.createObjectNode();
        body.set("error", error);
        return body;
    }
}
