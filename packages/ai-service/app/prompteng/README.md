# prompteng — Prompt 工程(内容生产者)

> 系统提示词的版本管理、热更新与使用归因。约 900 行,管理台 /v1/pe/* 的后端。

## 文件地图

| 文件 | 职责 |
|---|---|
| `models.py` | 4 张表:pe_templates / pe_template_versions / pe_usage_events / pe_metrics_daily |
| `service.py` | 核心:模板 CRUD、版本激活、`{{var}}` 渲染、激活缓存(`_CACHE`)与 rules 热更新 |
| `api.py` | /v1/pe/* 路由(模板 CRUD + activate/disable + metrics/overview + 最近装配) |
| `metrics.py` | 看板聚合:调用量/token/耗时按 模板×版本 归因;离线回归通过率 |

## 生命周期与热生效

```
新建(key 唯一,自动 v1 draft)→ add_version(draft,不影响线上)
  → activate(旧版本 archived + refresh_cache 热生效)
  → disable(回退代码默认,版本记录保留)
```

- **`_CACHE` 是主链路唯一读取点**(load_content 同步无 IO),agent/prompts.py 经裸钩子注入读取
- 渲染刻意不用 Jinja:`{{var}}` 简单替换,防模板注入
- `rules.*` 前缀模板激活时有副作用:调 `agent/prompts.py#register_rules` 热更新规则块

## 学习路径

1. `service.py#refresh_cache` 先读——理解缓存如何重建、rules 如何热更新
2. `service.py#activate` 看版本状态机(draft/active/archived 的不可变约束)
3. `metrics.py#overview` 看按版本归因怎么算(version=0 = 代码默认)
4. 消费方:`agent/prompts.py`(模板加载注入点)、`tools/rag.py`(工具描述覆盖)

## 优化切入点

- 缓存单进程内存:多实例需 Redis 失效广播(与 providers 同款问题)
- usage 事件的 prompt_tokens 来自 context 快照派生(估算),可接 usage 精确值
- 可加"草稿对比/灰度发布"能力(同 key 双版本分流)
