package com.v3agent.gateway.common;

import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;

/** 简单分页结果 */
@Data
@AllArgsConstructor
public class PageResult<T> {

    private long total;
    private List<T> list;
}
