# 告警模块改动计划

> 版本: v1(通知渠道 = 仅管理端 UI 看板展示)
> 涉及仓库: `model-gateway`(后端)、`ServerManegeUI`(管理端前端)
> 日期: 2026-08-26

## 1. 背景与目标

网关已有限流(`RateLimiter`)与熔断(`CircuitBreaker`),但两者触发时只有一行 `log.warn/debug`,管理端无感知。
本模块目标:

- 熔断打开、限流命中、失败率/时延/错误数超阈值时,**产生告警记录**;
- 管理端看板可**查看告警、配置告警规则、看到未读红点**;
- v1 不做 webhook/邮件等外发通知,不做 USER 维度告警。

### 分表决策(已确认)

不动现有 `policies` 表。新增两张表:

- `alert_rules` — 规则配置(与 policies 平级的配置表)
- `alert_records` — 触发记录(追加写的事件流水,独立于规则表)

理由: 限流/熔断策略是请求热路径的同步执行配置;告警规则是后台异步评估配置,触发历史又是高频追加流水,三者生命周期不同,合表会导致字段稀疏加剧。

## 2. 表设计

### 2.1 alert_rules(告警规则)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar UUID | 主键 |
| name | varchar(100) | 规则名 |
| metric | varchar(30) | `CIRCUIT_OPEN` / `RATE_LIMIT_HIT` / `FAILURE_RATE` / `AVG_LATENCY_MS` / `ERROR_COUNT` |
| target_type | varchar(20) | `GLOBAL` / `CHANNEL`(v1 不做 USER) |
| target_key | varchar(100) | CHANNEL 时为渠道 id,null = 全部渠道 |
| threshold | double | 阈值(失败率=百分比,时延=毫秒,其余=次数);CIRCUIT_OPEN 不用 |
| window_seconds | int | 统计窗口秒数(事件类指标不用) |
| cooldown_seconds | int | 静默期: 同规则同对象触发后不重复告警 |
| severity | varchar(10) | `INFO` / `WARN` / `CRITICAL` |
| enabled | int | 1 启用 / 0 停用 |
| remark | varchar(500) | |
| created_at / updated_at | datetime | |

### 2.2 alert_records(告警记录)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar UUID | 主键 |
| rule_id | varchar(36) | 触发规则(规则删除后记录保留) |
| rule_name | varchar(100) | 冗余快照,防规则改名后历史失真 |
| severity | varchar(10) | 冗余快照 |
| metric | varchar(30) | 冗余快照 |
| target_key | varchar(100) | 触发对象(渠道 id,全局为空) |
| metric_value | double | 触发时实际值(失败率 72.5、时延 830…),事件类为 null |
| message | varchar(500) | "渠道[xx] 60s 内失败率 72.5% ≥ 阈值 50%" |
| status | varchar(10) | `FIRING` / `RESOLVED` |
| read_flag | int | 0 未读 / 1 已读(看板红点依据) |
| created_at / resolved_at | datetime | |

索引(JPA `@Table(indexes=...)` 声明,沿用 ddl-auto=update 自动建表): `(status, read_flag)`、`(created_at)`、`(rule_id)`。

## 3. 后端改动(model-gateway)

新建包 `com.v3agent.gateway.alert`,全部为新文件,**不改动现有类的结构**,只在两个现有点位加钩子。

### 3.1 新文件清单

| 文件 | 职责 |
|---|---|
| `AlertRuleEntity.java` / `AlertRuleRepository.java` | 规则表 CRUD,`findByEnabled(1)` |
| `AlertRecordEntity.java` / `AlertRecordRepository.java` | 记录表;派生查询 `countByReadFlag(0)`、`findByStatusAndRuleIdAndTargetKey(...)`(静默期查重);`@Modifying` 批量已读 |
| `AlertRuleService.java` | 规则 CRUD + 内存缓存,`@Scheduled(fixedDelay=10_000)` 刷新 —— **完全照搬 `PolicyService` 的缓存模式** |
| `AlertMetrics.java` | 内存事件收集: 限流命中计数(按规则维度滑窗 deque)、熔断打开事件队列。被 RateLimiter/CircuitBreaker 钩子调用 |
| `AlertEvaluator.java` | 评估引擎,`@Scheduled(fixedDelay=15_000)`:<br>① 处理熔断打开事件 → 直接生成记录;<br>② 聚合 `invoke_logs` 计算 FAILURE_RATE / AVG_LATENCY_MS / ERROR_COUNT;<br>③ 统计窗口内限流命中数(RATE_LIMIT_HIT);<br>④ 超阈值且不在静默期 → 插 FIRING 记录;<br>⑤ 回落到阈值下 → 把活跃 FIRING 置 RESOLVED(填 resolved_at) |
| `AlertController.java` | `/api/alerts/rules` CRUD;`/api/alerts/records` 分页查询(状态/级别过滤);`PUT /records/{id}/read`、`PUT /records/read-all`;`GET /records/unread-count`(前端轮询红点) |

### 3.2 现有文件改动(仅 4 处,各几行)

| 文件 | 改动 |
|---|---|
| `CircuitBreaker.java` | `record()` 中 CLOSED→OPEN 转换处(约 L67)调用 `alertMetrics.onCircuitOpen(policy, channelId)`。用 setter 注入或 Spring 事件解耦,避免循环依赖 —— **方案: 发 `CircuitOpenEvent`(ApplicationEvent),AlertMetrics 监听**,最干净 |
| `RateLimiter.java` | `tryAcquire` 返回 false 处(约 L62)发 `RateLimitHitEvent`(policy id + targetKey + qpm/tpm 维度) |
| `InvokeLogRepository.java` | 加 1 个聚合查询: 按渠道聚合窗口内的 `count / avg(durationMs) / sum(status=0)`,供评估器算失败率/时延/错误数(复用现有 JPQL 投影接口风格) |
| `DataInitializer.java` | 种子 2 条默认规则(表为空时): ①"渠道熔断打开" CIRCUIT_OPEN / CRITICAL;②"全局失败率>50%(60s)" FAILURE_RATE / WARN |

### 3.3 关键语义

- **静默期**: 同 `(rule_id, target_key)` 存在 `created_at > now - cooldown` 的记录则跳过,不刷记录;
- **自动恢复**: 指标类规则在连续两次评估低于阈值时,把该规则活跃 FIRING 置 RESOLVED;CIRCUIT_OPEN 记录在该渠道熔断器回到 CLOSED 时 RESOLVED;
- **删除规则**: 只删规则,历史记录保留(rule_id 变"孤儿"可接受,已冗余 rule_name);
- **权限**: v1 全部用 `@RequirePermission(RequirePermission.SUPER)`(与 StatsController 一致)。不加新权限码 —— 避免已有数据库因种子逻辑(count==0 才种)拿不到 `alert:manage` 权限。

## 4. 前端改动(ServerManegeUI)

| 文件 | 改动 |
|---|---|
| `src/api/modules/alert.ts` | 新增,照 `policy.ts` 模式: rules CRUD、records 分页、unreadCount、markRead/markAllRead |
| `src/types/index.ts` | 加 `AlertRule` / `AlertRecord` 类型 |
| `src/views/Alerts/index.vue` | 新页面,两个 Tab:<br>**告警记录**: 表格(级别标签颜色/消息/触发值/时间/状态),未读高亮,支持单条已读、全部已读、按状态/级别筛选;<br>**规则管理**: 表格 + 新建/编辑对话框(指标类型下拉联动显隐 threshold/window 字段)、启用开关、删除 |
| `src/router/index.ts` | 加 `/alerts` 路由 |
| `src/layout/`(菜单组件) | 加"告警中心"菜单项,图标旁挂未读数 Badge;布局里 30s 轮询 `unread-count`(与 stats realtime 轮询同模式) |

## 5. 验证计划

1. `mvn -o compile` 编译通过;
2. 重启网关(kill 旧 java 进程树再启动,确保新类加载),确认自动建出 `alert_rules` / `alert_records` 及种子规则;
3. **触发熔断告警**: 把一个渠道 baseUrl 改成不可达地址,调 5+ 次模型接口(样本≥5 且全失败)→ 熔断打开 → 看板出现 CRITICAL 记录 + 红点;
4. **触发失败率告警**: 恢复渠道后再制造部分失败,观察 FIRING → 恢复后两次评估周期(≈30s)自动 RESOLVED;
5. **触发限流告警**(若配 RATE_LIMIT_HIT 规则): 建一个小 QPM 策略,连续刷接口 → 429 同时产生记录;
6. 前端: 规则 CRUD、启用开关、已读/全部已读、红点消除;
7. 回归: 确认限流/熔断原有行为不变(QPM 429、熔断跳渠道、TPM 预扣结算)。

## 6. v1 明确不做

- webhook / 邮件 / 企业微信等外发通知(记录表的 `read_flag`/`status` 设计已为以后外发预留 `notified` 语义位置);
- USER 维度告警;
- 告警升级/分派/认领流程;
- `policies` 表拆表及数据库层约束(与本次无关,另行处理)。
