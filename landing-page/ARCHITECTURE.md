# Tikpan AI 聚合平台落地蓝图

这份文档对应当前 `landing-page` 原型里的四个产品面：

- 创作工作台：用户选择能力、填写参数、提交任务。
- 模型目录：按用户场景展示平台模型，不展示真实上游。
- 供应链后台：管理供应商、真实模型、渠道、参数映射、价格。
- 任务监控：管理任务、失败、成本、退款、日志。

## 1. 核心原则

用户只看到平台能力：

```text
图像生成 Pro
视频生成 Story
智能对话 Assistant
声音生成 Voice
电商素材工作流
```

后台维护真实供应链：

```text
Provider -> Provider Model -> Channel -> Parameter Mapping -> Routing Policy
```

不要让普通用户选择 `Relay A`、`openai/gpt-image-1`、`seedance-video-fast` 这类上游细节。

## 2. 推荐后端模块

```text
api-gateway
  登录、鉴权、统一 API、限流

orchestrator
  校验 capability schema
  选择平台模型
  过滤可用渠道
  参数映射
  创建任务
  预冻结余额

provider-adapters
  relay_a
  relay_b
  official_c
  comfyui_hosted

worker
  异步执行图片/视频/音频任务
  轮询上游任务
  下载媒体到 R2
  更新任务状态

billing
  充值、冻结、结算、退款、赠送余额

admin
  供应商、模型、渠道、价格、映射、路由、日志
```

## 3. API 设计

### 用户侧

```http
GET /v1/capabilities
```

返回前台可展示能力和平台模型。

```http
GET /v1/models/{platform_model_id}/schema
```

返回动态表单字段，前端按 schema 渲染。

```http
POST /v1/tasks
```

请求：

```json
{
  "model": "tikpan.image.pro",
  "input": {
    "prompt": "明亮干净的护肤品商品图",
    "aspect_ratio": "1:1",
    "quality": "high"
  },
  "routing": {
    "mode": "quality"
  }
}
```

响应：

```json
{
  "task_id": "task_72ca",
  "model": "tikpan.image.pro",
  "status": "queued",
  "estimated_cost": "0.18",
  "estimated_time": "8-15 秒",
  "guarantee": "失败不扣费，成功后结算"
}
```

```http
GET /v1/tasks/{task_id}
```

返回任务状态、进度、结果 URL、用户可见错误。

### 管理后台

```http
GET /admin/providers
POST /admin/providers
PATCH /admin/providers/{provider_id}
```

```http
GET /admin/platform-models
POST /admin/platform-models
PATCH /admin/platform-models/{model_id}
```

```http
GET /admin/channels
POST /admin/channels
PATCH /admin/channels/{channel_id}
```

```http
POST /admin/channels/{channel_id}/test
```

用于测试参数映射后的真实 payload 和上游响应。

## 4. 数据库表

### providers

```sql
create table providers (
  id text primary key,
  name text not null,
  kind text not null,
  base_url text not null,
  auth_type text not null,
  encrypted_api_key text not null,
  status text not null default 'active',
  rpm integer,
  concurrency integer,
  timeout_ms integer not null default 60000,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### provider_models

```sql
create table provider_models (
  id text primary key,
  provider_id text not null references providers(id),
  upstream_model_name text not null,
  endpoint_type text not null,
  modality text not null,
  status text not null default 'active',
  raw_capabilities jsonb not null default '{}',
  notes text,
  created_at timestamptz not null default now()
);
```

### platform_models

```sql
create table platform_models (
  id text primary key,
  name text not null,
  short_name text not null,
  modality text not null,
  tier text not null,
  description text not null,
  use_cases jsonb not null default '[]',
  visible boolean not null default true,
  recommended boolean not null default false,
  sort_order integer not null default 0,
  schema jsonb not null default '[]',
  created_at timestamptz not null default now()
);
```

### model_channels

```sql
create table model_channels (
  id text primary key,
  platform_model_id text not null references platform_models(id),
  provider_id text not null references providers(id),
  provider_model_id text not null references provider_models(id),
  role text not null,
  status text not null default 'active',
  weight integer not null default 50,
  priority integer not null default 100,
  cost_price numeric,
  sale_price numeric,
  billing_unit text not null,
  max_concurrency integer,
  timeout_ms integer,
  success_rate numeric,
  avg_latency_ms integer,
  supports jsonb not null default '[]',
  created_at timestamptz not null default now()
);
```

### channel_parameter_mappings

```sql
create table channel_parameter_mappings (
  id text primary key,
  channel_id text not null references model_channels(id),
  platform_param_key text not null,
  upstream_param_key text,
  supported boolean not null default true,
  transform text not null default 'direct',
  value_map jsonb not null default '{}',
  default_value jsonb,
  omit_if_unsupported boolean not null default true
);
```

### tasks

```sql
create table tasks (
  id text primary key,
  user_id text not null,
  platform_model_id text not null references platform_models(id),
  status text not null,
  input jsonb not null,
  output jsonb,
  estimated_cost numeric,
  final_cost numeric,
  public_error_code text,
  public_error_message text,
  created_at timestamptz not null default now(),
  queued_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz
);
```

### task_attempts

```sql
create table task_attempts (
  id text primary key,
  task_id text not null references tasks(id),
  provider_id text not null references providers(id),
  provider_model_id text not null references provider_models(id),
  channel_id text not null references model_channels(id),
  status text not null,
  mapped_payload jsonb not null,
  upstream_response jsonb,
  upstream_error_code text,
  latency_ms integer,
  cost_price numeric,
  created_at timestamptz not null default now()
);
```

### wallet_ledger

```sql
create table wallet_ledger (
  id text primary key,
  user_id text not null,
  task_id text references tasks(id),
  type text not null,
  amount numeric not null,
  balance_after numeric not null,
  note text,
  created_at timestamptz not null default now()
);
```

账务类型建议：

```text
recharge
gift
pre_authorize
settle
release
refund
admin_adjust
```

## 5. 任务状态

```text
created
queued
running
polling
saving_media
completed
failed
cancelled
expired
```

用户可见状态要更简单：

```text
排队中
生成中
整理结果中
已完成
生成失败
```

## 6. 扣费规则

图片、视频、音频建议：

```text
创建任务 -> 预冻结预计费用 -> 成功后正式结算 -> 失败释放冻结
```

聊天模型建议：

```text
创建请求 -> 检查余额 -> 根据实际 token 结算 -> 异常时不扣费或按已完成部分结算
```

不要直接在请求前永久扣费，否则失败退款和用户投诉会很难处理。

## 7. 媒体文件策略

输入文件：

```text
用户 -> R2/S3 预签名上传 -> 后端拿 object_key -> 上游读取临时 URL
```

输出文件：

```text
上游返回 URL -> Worker 下载 -> 上传 R2 -> 数据库保存 object_key -> 前端展示 CDN URL
```

数据库只保存：

```text
object_key
mime_type
size
duration
width
height
hash
```

不要把图片、视频本体放进数据库，也不要长期依赖上游临时 URL。

## 8. 错误映射

上游错误不要直接给用户看。

```text
TIMEOUT -> 生成超时，请稍后重试
429 -> 当前排队人数较多，请稍后再试
NO_BALANCE -> 余额不足，请先充值
FORMAT_ERROR -> 上传文件格式不符合要求
CONTENT_REJECTED -> 当前内容无法生成，请调整描述
PROVIDER_DOWN -> 当前服务繁忙，系统已尝试切换备用线路
```

后台日志保留真实错误：

```text
provider
upstream_model
raw_error_code
raw_error_body
mapped_error_code
task_id
attempt_id
```

## 9. 第一版落地顺序

1. 做用户、登录、钱包和充值。
2. 做 `providers`、`platform_models`、`model_channels` 后台 CRUD。
3. 把当前 `src/orchestrator.ts` 逻辑迁移到后端。
4. 先接 1 个图片供应商、1 个视频供应商、1 个聊天供应商。
5. 做任务表、任务轮询、失败释放冻结。
6. 做 R2 上传和输出归档。
7. 做后台日志、成本统计和错误映射。
8. 最后再做复杂的模型市场、团队空间和开发者 API。

## 10. 当前前端原型对应关系

```text
src/productData.ts
  模拟数据库里的 providers、platform_models、model_channels、tasks

src/orchestrator.ts
  模拟后端 orchestrator、router、parameter mapper、billing preauth

src/App.tsx
  产品控制台、用户工作台、模型目录、供应链后台、任务监控
```

下一步接真实后端时，优先替换数据来源，而不是重写 UI。
