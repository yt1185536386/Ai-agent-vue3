# ServerManegeUI — 模型服务网关管理界面

Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia,对接 `../model-gateway`(Java Spring Boot)。

## 模块

- **登录** `/login`(初始账号 `admin / admin123`)
- **数据概览** `/dashboard` — 调用量 / Token / QPM / TPM / 错误率卡片,渠道、模型、用户、趋势四维图表(用户维度为 用户×模型 堆叠柱状图),支持时间范围 / 用户筛选 / 自动刷新 / CSV 导出
- **模型调用** `/invoke` — 调试台,选择渠道模型直接对话
- **仓库管理** `/channels` — 模型渠道(提供方)接入点管理
- **用户管理** `/users` — 账号 CRUD、启禁用、重置密码
- **团队管理** `/teams` — 团队 CRUD、成员加入/移出、成员/负责人角色切换
- **调用日志** `/logs`、**限流熔断** `/policies`

## 运行

```bash
npm install
npm run dev     # http://localhost:6013,/api 与 /v1 代理到 http://localhost:6012
npm run build   # 类型检查 + 产物构建
```

先启动后端:`cd ../model-gateway && mvn spring-boot:run`(默认 H2,开箱即用)。
