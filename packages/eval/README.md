# v3agent Eval

独立的轻量评测包:用真实模型跑用例,量化 Agent 的工具选择、流程完成度、回答质量与提示词回归。

与三个服务平级,**不进任何服务的运行路径**;以 in-process 方式直接调用
`ai-service` 的 harness(保证测的就是线上跑的那套装配)。

## 运行

必须用 ai-service 的 venv(零新增依赖):

```bash
cd packages/eval
../ai-service/.venv/Scripts/python run_eval.py                     # 全部套件
../ai-service/.venv/Scripts/python run_eval.py --suite tool_selection
../ai-service/.venv/Scripts/python run_eval.py --suite regression --model qwen-plus
../ai-service/.venv/Scripts/python run_eval.py --suite quality --judge qwen-max
```

参数:

| 参数 | 默认 | 说明 |
|---|---|---|
| `--suite` | all | tool_selection / e2e / quality / regression / retrieval |
| `--provider` | bailian | 被测模型来源(company/bailian) |
| `--model` | qwen-plus | 被测模型 |
| `--judge-provider` | 同 provider | 裁判模型来源 |
| `--judge` | `EVAL_JUDGE_MODEL` 或 qwen-max | 裁判模型 |
| `--no-save` | 关 | 不写 reports/*.json |
| `--no-upload` | 关 | 不上报日聚合指标(cx/pe_metrics_daily) |
| `--strategy` | 无 | 检索策略标识(报告标签,多策略对比用) |
| `--top-k` / `--threshold` | 当前策略 | 检索参数覆盖(同 ground truth 对比多策略) |
| `--user-id` | eval | 检索目标用户(chunks 按用户隔离) |
| `--export-retrieval` | 关 | 从 cx_eval_cases 导出 suites/retrieval.json 后退出 |

退出码:全部通过 0,有失败 1(可直接接 CI)。

## 前置条件

- `ai-service/.env` 已配置(模型网关密钥、DATABASE_URL)
- 涉及用户权限**写操作**的 e2e 用例需要 NestJS(6011)在线
- 涉及真实仓库数据的用例需要 MySQL 里有对应物料

## 四个套件与用例格式

用例在 `suites/*.json`,直接加条目即可。

### tool_selection — 工具选择准确率

```json
{ "id": "weather-basic", "input": "长沙今天天气怎么样", "expect": ["get_weather"] }
```

- `expect`:期望的工具调用序列,默认**子序列匹配**(允许模型穿插 get_current_time 等合理调用)
- `"match": "exact"` 时严格相等(用于「不该调工具」的用例:`"expect": []`)
- 可选 `user_id`(默认 "eval")

### e2e — 端到端流程成功率

多轮脚本,逐步断言;撞上 interrupt 审批时按 `approve` 自动批准/拒绝并恢复。当前 Agent 不再包含仓库/权限类变更工具,用例主要覆盖通用工具链与对话上下文。

```json
{
  "id": "weather-then-calc",
  "user_id": "eval",
  "steps": [
    { "user": "长沙今天天气怎么样", "expect_tools": ["get_weather"] },
    { "user": "把刚才说的最高温度乘以 2 是多少", "expect_tools": ["calculator"] }
  ]
}
```

- 每步的 `expect_tools` 只检查**本步新增**的工具调用
- 步骤不带 `approve` 时出现审批中断判失败

### quality — 回答质量 LLM 评分

```json
{ "id": "asset-flow-explain", "input": "...", "rubric": "回答必须…;不得…", "pass_score": 4 }
```

裁判模型按 rubric 打 1-5 分,`>= pass_score`(默认 4)判过。

### regression — Prompt 回归测试

走直答路径(与线上 preprocess 一致:时间注入 + 思考模式规整),
改系统提示词或换模型后跑一遍防退化:

```json
{ "id": "math-fact", "input": "(3+5)*2?", "assert": { "type": "contains", "value": "16" } }
```

断言类型:`contains` / `regex` / `judge`(value 为 rubric,可配 pass_score)。

### retrieval — 检索召回评测(Recall@K / Precision@K)

in-process 直调 `search_chunks()`(与线上同一实现),对 ground truth 计算
Recall@K / Precision@K / 零结果率——切分/相似度调优的裁判指标:

```json
{ "id": "case1", "query": "猫怎么喂", "expect_doc_ids": ["doc-cat"], "expect_contains": ["喂食"] }
```

- 用例来源:`suites/retrieval.json` 由 `--export-retrieval` 从 `cx_eval_cases`
  (enabled)导出;线上零结果 query 可在管理台「检索与快照」页一键回收为用例;
- 单条 passed 判据:recall == 1(期望文档全部命中)且内容断言通过;
- `--top-k` / `--threshold` 覆盖检索参数,同一份 ground truth 可对比多策略;
- 聚合指标自动上报 `cx_metrics_daily`(Recall@K / Precision@K 上板)。

### guardrail — 前置守门(意图判定 + 越权校验)

> 已移除:原 `app/guardrail.py` 子图与对应套件在 2026-08 权限重构时删除,
> 越权与业务规则改由 NestJS 规则引擎统一处理。

## 报告

控制台打印明细 + 汇总;`reports/eval-<时间戳>.json` 落盘完整结果
(含每条的耗时、评分、失败原因),可用于跨版本对比。

跑完默认把离线指标上板(retrieval → `cx_metrics_daily`,regression/quality
→ `pe_metrics_daily`,按模板当前版本归因),管理台「Context 监控」页可直接看到
Recall@K / Precision@K 趋势线;`--no-upload` 关闭。默认 in-process 直写;
设 `EVAL_REPORT_URL=http://localhost:6010` 时改走 HTTP POST `/v1/cx/metrics/report`。

## 结构

```
eval/
  run_eval.py       CLI 入口
  core/
    client.py       挂载 ai-service、加载 .env、构造被测 Agent
    runners.py      五个套件执行器
    suitegen.py     retrieval 套件生成器(cx_eval_cases → suites/retrieval.json)
    judge.py        LLM 裁判(rubric → {score, reason})
    report.py       控制台表格 + JSON 落盘 + 离线指标上板
  suites/*.json     用例数据
  reports/          运行产物(不入库)
```
