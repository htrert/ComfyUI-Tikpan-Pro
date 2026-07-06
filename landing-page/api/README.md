# Tikpan Internal AI Workspace API

这是一个内部可配置的 AI 聚合工作台后端骨架，不是对外开放 API 平台。

平台链路：

```text
用户 Web
→ Tikpan API
→ 任务队列 / Worker
→ 内部 ProviderKey 池
→ 上游供应商
→ 对象存储 / 作品库
→ 前台展示
```

当前边界：

- 用户只登录 Tikpan 工作台。
- 上游供应商 key 由平台统一持有和调度。
- 用户余额消耗在 Tikpan 钱包，平台再消耗上游 key 额度。
- 用户侧接口只返回任务、钱包、作品等产品信息。
- 上游 provider、provider key、真实 payload、错误详情只进入管理后台和日志。
- 不提供第三方 API Key、SDK、Webhook、外部开发者接入或 ComfyUI 节点调用平台 API。

## 已覆盖能力

- 平台模型和真实上游模型分离。
- 一个平台模型绑定多个上游渠道。
- 每个渠道配置参数映射、成本价、销售价、优先级、权重。
- 内部 `ProviderKey` 池支持多 key、RPM、TPM、并发、冷却、优先级和健康状态。
- `ProviderKey` 领取使用 lease，包含 `leaseId`、`expiresAt` 和过期回收，避免 Worker 崩溃后永久占用。
- PostgreSQL 模式使用事务和行锁领取 key；内存模式用于本地验证。
- TPM 在调用前预估占用，调用后根据上游 usage 修正。
- 任务创建时预冻结余额，成功后结算，失败/取消后释放。
- 钱包流水对同一 task 的冻结、结算、释放、退款做幂等保护。
- Worker 异步领取任务并执行上游调用。
- 失败时自动尝试备用渠道。
- 上游错误归一成用户友好文案，真实错误保留在后台 attempt 日志。
- 输出媒体可转存对象存储并进入作品库。

## 运行

```bash
cd landing-page/api
npm run dev
```

默认地址：

```text
http://localhost:8787
```

检查：

```bash
npm run check
```

## 运维文档

```text
docs/STATE_MACHINES.md
  任务、钱包、ProviderKey、ModelChannel 的状态和转移规则。

docs/FAILURE_HANDLING.md
  失败退款、失败重试、ProviderKey 冷却、用户友好错误和告警触发。

docs/ROUTING_STRATEGY.md
  平台模型到渠道、ProviderModel、ProviderKey 的路由和 fallback 策略。

docs/LAUNCH_CHECKLIST.md
  小规模商用上线前检查清单。

docs/RELEASE_SOP.md
  正式发布、灰度、观察和放量流程。

docs/UPDATE_AND_ROLLBACK.md
  后续功能更新、数据库迁移、回滚和对账流程。

docs/DOCKER_RELEASE.md
  Docker 镜像构建、服务器更新、docker compose 部署和回滚命令模板。

alerts.json
  ProviderKey、渠道、队列、钱包、数据库等告警规则。
```

## 用户侧接口

这些接口面向平台前台，不是第三方开放 API。

```http
GET /health
GET /v1/capabilities
GET /v1/models/{platform_model_id}/schema
POST /v1/routes/preview
POST /v1/tasks
GET /v1/tasks/{task_id}
POST /v1/tasks/{task_id}/cancel
POST /v1/tasks/{task_id}/retry
GET /v1/wallet
GET /v1/assets
```

创建图片任务：

```bash
curl -X POST http://localhost:8787/v1/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"tikpan.image.gpt-image-2-4k\",\"input\":{\"prompt\":\"明亮干净的护肤品商品图\",\"size\":\"1024x1024\",\"quality\":\"high\"},\"routing\":{\"mode\":\"quality\"}}"
```

## 管理后台接口

```http
GET /admin/providers
POST /admin/providers
GET /admin/provider-keys
POST /admin/provider-keys
PATCH /admin/provider-keys/{provider_key_id}
GET /admin/platform-models
GET /admin/provider-models
GET /admin/channels
GET /admin/tasks
GET /admin/wallet-ledger
GET /admin/audit-logs
```

`/admin/provider-keys` 会返回脱敏后的 key 状态，例如并发、RPM 窗口、冷却时间、最近错误；不会返回原始密钥。

后台操作建议只开放高价值、可审计动作：

```text
查看和禁用 ProviderKey
调整 ProviderKey 限额和冷却
调整模型/渠道价格
调整渠道优先级和权重
查看任务详情与失败原因
手工补偿 / 退款
查看审计日志
查看监控指标
```

## 核心数据模型

```text
Provider
  上游供应商，例如官方模型平台、中转平台、私有网关。

ProviderKey
  供应商 key，是平台内部基础设施资源，可单独限流、冷却和禁用。

ProviderModel
  上游真实模型。

PlatformModel
  前台展示给用户的模型。

ModelChannel
  平台模型到上游模型的绑定关系。

ChannelParameterMapping
  平台参数到上游参数的映射。

Task
  用户提交的一次平台任务。

TaskAttempt
  一次真实上游调用记录，后台保留 provider_key_id、真实错误和 fallback 原因。

WalletLedger
  预冻结、结算、释放、退款等钱包流水。
```

## 并发模型

并发分三层控制：

```text
前台请求并发：页面、余额、任务状态查询。
任务提交并发：创建任务、预冻结余额、入队。
上游执行并发：Worker 调用供应商，由 Channel 和 ProviderKey 控制。
```

一开始建议的 Worker 上游并发：

```text
chat: 20
image: 10
video: 2
audio: 5
```

真实瓶颈通常在 ProviderKey 的 RPM/TPM、供应商排队速度、视频任务耗时和对象存储转存带宽。

## 环境变量

```text
TIKPAN_PROVIDER_ADAPTER=mock|http
TIKPAN_PROVIDER_SECRETS={"pkey-cangyuan-main":"sk-...","cangyuan":"sk-legacy-provider-secret"}
TIKPAN_SECRETS_ENCRYPTION_KEY=replace-with-32-byte-production-secret
TIKPAN_WORKER_ENABLED=true
TIKPAN_WORKER_POLL_INTERVAL_MS=750
TIKPAN_WORKER_LOCK_TTL_MS=120000
```

`TIKPAN_PROVIDER_SECRETS` 优先按 `provider_key_id` 取密钥，其次才按 `provider_id` 兼容旧配置。

`TIKPAN_SECRETS_ENCRYPTION_KEY` 配置后，后台写入的 ProviderKey 会以 AES-256-GCM 的 `enc:v1:` 格式保存。后台列表只返回脱敏信息，不返回明文 key。

## 生产加固说明

当前 PostgreSQL 模式已经覆盖：

```text
ProviderKey 行锁原子领取
lease 过期回收
RPM/TPM 分钟窗口
调用前 TPM 预占
调用后 usage 修正
错误类型分级冷却
钱包结算幂等
后台 key 脱敏
```

如果后续 Worker 数量很多，建议把 ProviderKey RPM/TPM 窗口迁移到 Redis Lua 或 Redis Cell，避免数据库承担高频令牌桶压力。

并发 smoke test：

```bash
npm run smoke:provider-keys
```

告警规则检查：

```bash
node scripts/check-alerts.mjs
```

Docker 发布参考：

```bash
docker build -t registry.example.com/tikpan/api:2026.07.05-1 .
docker compose -f docker-compose.prod.yml pull api worker
docker compose -f docker-compose.prod.yml up -d api worker
```
