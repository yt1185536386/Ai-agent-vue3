# persistence — 展示轨道持久化

> 双轨制的一半:messages 表(前端气泡的唯一权威)。约 110 行。

## 文件地图

| 文件 | 职责 |
|---|---|
| `display.py` | 用户/助手消息落库(fail-soft)+ regenerate 截断(显式报错)+ 老会话回填投影 |

## 核心设计:双轨制(模块 docstring 原文)

- `checkpoints.db`(SQLite,agent/loop.py)是**推理轨道**唯一权威
- MySQL messages 表是**展示轨道**唯一权威
- 两端写入全在服务端;前端只带本轮新消息

失败策略分级(关键):

| 操作 | 失败策略 | 原因 |
|---|---|---|
| 常规落库 | fail-soft(打日志继续) | 不影响推理流程 |
| regenerate 截断 | **抛异常** | 截断失败而图已分叉 → 两轨永久分叉 |

## 学习路径

1. 先读本 README 的双轨制,再对照 `agent/loop.py` 的 checkpointer
2. `display.py` 按函数读:`persist_user_message`(进图前落,图失败不丢)→ `persist_assistant_message`(终止补占位/空气泡不落)→ `load_display_history`(老会话一次性回填的投影规则)

## 优化切入点

- 落库是每请求同步 await:高并发下可改为后台任务(参照 contexteng/collector.py 的 _submit 模式)
- 老会话回填每次首请求都跑一遍查询,可加"已回填"标记
