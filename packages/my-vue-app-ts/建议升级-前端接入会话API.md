# 建议升级：前端接入 FastAPI 会话/REST(步骤 6c)

> 当前状态:后端四层架构 + RAG 已完整落地,前端仍用 `localStorage` 存会话。
> 本文档记录升级方案与权衡,**留待后续实施**,不是必做。

---

## 一、为什么不接入

| 现状问题 | 长期影响 |
| --- | --- |
| 会话存在浏览器 localStorage | 换设备 / 清缓存 / 隐身模式即丢失 |
| 多端不同步 | 公司 / 家里的两台电脑是两套历史 |
| 后端 RAG 已实现但前端未暴露上传入口 | 用户感知不到 RAG,投入闲置 |
| localStorage 上限 ~5MB | 长对话 + base64 图片容易爆 |
| 无用户隔离 | 鉴权 / 限额 / 共享都做不了 |

## 二、接入后能得到

- **RAG 真用起来**:侧栏"+"菜单接 `/v1/documents`,上传即建索引,后续提问自动注入上下文
- **数据持久**:换设备 / 清缓存都不丢
- **多端同步**:公司发的对话,回家接着续
- **多用户基础**:为将来登录 / 共享 / 团队协作打地基

## 三、改动面

后端不动,只改 `my-vue-app-ts/` 前端。

### 3.1 最小改动清单(预计半天)

| 文件 | 改动 |
| --- | --- |
| `mixin.ts` | 加 `user_id`(临时 `Eric_8849`)、所有 fetch 自动带 `X-User-Id` 头 |
| `mixin.ts` `loadConvs` | 改为 `GET /v1/conversations`,失败回退 localStorage 缓存(平滑过渡) |
| `mixin.ts` `newChat` | 改为 `POST /v1/conversations` |
| `mixin.ts` `selectConv` | 按需 `GET /v1/conversations/{id}` 拉详情 |
| `mixin.ts` `removeConv` | 改为 `DELETE /v1/conversations/{id}` |
| `mixin.ts` `handleSend` | 用户消息发送后 `POST /v1/conversations/{id}/messages`(role=user);助手回答完成 `POST ...`(role=assistant) |
| `mixin.ts` 上传逻辑 | 附件走 `POST /v1/documents` 而不是 `POST /v1/files/upload`(NestJS 旧接口保留兼容) |
| `index.vue` "+" 菜单 | 新增"上传文档"入口(目前只有图片 / 文档选择) |

### 3.2 关键设计取舍

- **user_id 临时方案**:登录体系还没做,先用 `Eric_8849` 占位(本地存 localStorage),后续接 JWT 时无缝替换为解析后的真用户 ID
- **乐观更新 + 后台落库**:用户消息先写本地数组(`messages.push`)立刻显示,异步 `POST /messages` 保存;失败 toast 提示但不影响聊天
- **离线降级**:网络失败时回退 localStorage 缓存(保留现有 localStorage 逻辑兜底)
- **附件兼容**:文档附件仍走 FastAPI 的 `/v1/documents` 走 RAG 路径;图片附件继续 base64 走消息体(实时发给模型,不入库浪费)
- **NestJS 的 `/v1/files` 接口**:不再使用,可保留一段时间兼容旧客户端再下线

### 3.3 不在本次范围内

- 流式响应本身的保存逻辑(流式结束再 POST 一次即可,无需逐 token 落库)
- 错误重试 / 断线续传
- 多用户登录页 / JWT
- 历史会话的搜索、标签、收藏

---

## 四、验证清单(实施时用)

1. 新建会话 → 数据库有 1 条 conversation 记录
2. 发消息 → messages 表追加 user/assistant 各 1 条,position 递增
3. 删除会话 → 数据库 conversation 与 messages 都清空
4. 刷新页面 → 从数据库拉回历史
5. 上传文档 → Document + Chunk 表都有记录;提问自动注入相关 chunk

## 五、启动顺序(实施时)

```bash
# 1. 启动后端
cd ai-service && .venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
# 2. 启动网关
cd NestJS && npm run start:dev
# 3. 启动前端
cd my-vue-app-ts && npm run dev
```

---

> 实施时建议拆成两个 commit:
> ① 加 `user_id` 与会话 CRUD(读路径)
> ② 加消息持久化与文档上传(写路径)
>
> 每步独立可回滚,降低回归风险。