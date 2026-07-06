# 前后端联调说明

当前项目已经有两个运行面：

- 前端产品控制台：`landing-page`
- 后端 API demo：`landing-page/api`

## 1. 启动后端 API

打开第一个终端：

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
curl http://localhost:8787/health
```

应该返回：

```json
{
  "data": {
    "status": "ok"
  }
}
```

## 2. 启动前端

打开第二个终端：

```bash
cd landing-page
npm run dev
```

默认地址：

```text
http://localhost:5173
```

## 3. 在页面里切换执行模式

进入「创作工作台」后，在「结果预览」右上角可以看到两个模式：

```text
本地模拟
后端 API
```

### 本地模拟

直接调用前端 `src/orchestrator.ts`。

适合：

- 快速看 UI
- 不启动后端
- 演示路由、参数映射、计费预览

### 后端 API

调用：

```text
POST http://localhost:8787/v1/tasks
```

适合：

- 验证前后端接口
- 看后端返回的 provider、真实模型和 mapped payload
- 后续替换为真实数据库和真实供应商

## 4. 修改 API 地址

默认前端会请求：

```text
http://localhost:8787
```

如果要改成其他地址，可以新建 `.env.local`：

```bash
VITE_TIKPAN_API_URL=http://localhost:8787
```

改完后重启前端 dev server。

## 5. 手动创建任务

PowerShell 示例：

```powershell
$body = @{
  model = "tikpan.image.pro"
  input = @{
    prompt = "明亮干净的护肤品商品图"
    aspect_ratio = "1:1"
    quality = "high"
  }
  routing = @{ mode = "quality" }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod `
  -Uri "http://localhost:8787/v1/tasks" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

## 6. 当前联调链路

```text
用户点击「开始生成」
  -> src/apiClient.ts
  -> POST /v1/tasks
  -> api/src/server.mjs
  -> api/src/orchestrator.mjs
  -> api/src/store.mjs
  -> 返回任务、渠道、payload、预冻结信息
  -> 前端 TaskPreview 展示
```

## 7. 任务生命周期

当前 API demo 会模拟 Worker 执行进度。前端在「后端 API」模式下创建任务后，会每 1.2 秒轮询：

```text
GET http://localhost:8787/v1/tasks/{task_id}
```

状态流转：

```text
queued -> running -> saving_media -> completed
```

页面会展示 `progress`、`current_step` 和完成后的 `output.publicUrls`。真实接入时，可以把这个模拟逻辑替换成队列 Worker、Webhook 回调或 provider adapter 的状态同步。

## 8. 后台渠道配置

供应链后台现在支持直接编辑当前平台模型下的渠道：

- 状态：`active` / `degraded` / `disabled`
- 角色：`primary` / `backup` / `cheap` / `fast` / `quality`
- 权重：`0-100`
- 成本价和销售价

在「本地模拟」模式下，编辑会立即影响前端本地路由。在「后端 API」模式下，编辑会同步到：

```text
PATCH http://localhost:8787/admin/channels/{channel_id}
```

示例：

```powershell
$body = @{
  status = "disabled"
  weight = 0
  cost_price = 0.11
  sale_price = 0.18
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8787/admin/channels/ch-image-a" `
  -Method Patch `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

这条配置会影响后续 `POST /v1/tasks` 和 `POST /v1/routes/preview` 的路由选择。

## 9. 钱包与账务

后端 API demo 现在有内存版钱包：

```text
GET  http://localhost:8787/v1/wallet
POST http://localhost:8787/v1/wallet/top-ups
GET  http://localhost:8787/admin/wallet-ledger
```

账务流转：

```text
充值 top_up
  -> 创建任务 pre_authorize，余额减少，冻结金额增加
  -> 任务成功 settle，冻结金额减少
  -> 任务失败 release，冻结金额释放回余额
```

余额不足时，`POST /v1/tasks` 会返回：

```text
402 NO_BALANCE
```

PowerShell 充值示例：

```powershell
$body = @{
  amount = 10
  note = "演示充值"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8787/v1/wallet/top-ups" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

前端顶部会显示可用余额和冻结金额；「任务监控」页会显示最近账务流水。

## 10. 平台 API Key

用户不需要去上游供应商获取 Key。后台可以给用户签发你平台自己的 API Key：

```text
GET   http://localhost:8787/admin/api-keys
POST  http://localhost:8787/admin/api-keys
PATCH http://localhost:8787/admin/api-keys/{key_id}
```

创建 Key 示例：

```powershell
$body = @{
  name = "客户 A 生产 Key"
  scopes = @("tasks:create", "wallet:read")
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8787/admin/api-keys" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

外部调用任务接口时使用平台 Key：

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8787/v1/tasks" `
  -Method Post `
  -Headers @{ Authorization = "Bearer tk_xxx" } `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

后端会根据平台 Key 找到平台用户，再使用该用户的钱包余额、路由策略和供应链配置。撤销后的 Key 会返回：

```text
401 INVALID_API_KEY
```

## 11. 下一步真实化

1. 前端模型目录从 `/v1/capabilities` 获取。
2. 前端表单 schema 从 `/v1/models/{id}/schema` 获取。
3. 后台供应链页面从 `/admin/channels` 获取。
4. `api/src/store.mjs` 换成 PostgreSQL。
5. `api/src/orchestrator.mjs` 接真实 provider adapter。
6. Worker 执行任务并写回 `/v1/tasks/{id}` 状态。
## 12. 失败重试与备用渠道

图片模型现在可以演示主渠道超时后的自动切换。前端在「高级设置」里打开「模拟主渠道超时」后，会提交平台控制字段 `simulate_failover`。这个字段只用于路由和演示，不会映射到上游供应商 payload。

PowerShell 示例：

```powershell
$body = @{
  model = "tikpan.image.pro"
  input = @{
    prompt = "明亮干净的护肤品商品图"
    aspect_ratio = "1:1"
    quality = "high"
    simulate_failover = $true
  }
  routing = @{ mode = "quality" }
} | ConvertTo-Json -Depth 6

$task = Invoke-RestMethod `
  -Uri "http://localhost:8787/v1/tasks" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

Start-Sleep -Seconds 7

Invoke-RestMethod `
  -Uri "http://localhost:8787/v1/tasks/$($task.data.task_id)" |
  ConvertTo-Json -Depth 10
```

预期结果：

- `status` 最终为 `completed`
- `attempts[0]` 为 `failed`，错误码为 `PROVIDER_TIMEOUT`
- `attempts[1]` 为 `completed`，并带有 `fallback_reason`
- 前端「后台内部对象」会展示两次调用尝试，方便演示平台的稳定性能力

## 13. Admin API protection

By default the demo keeps `/admin/*` open so local product verification is easy. For any shared, staging, or production-like environment, set an admin token before starting the API:

```powershell
$env:TIKPAN_ADMIN_TOKEN = "replace-with-a-long-random-admin-token"
cd landing-page/api
npm run dev
```

When `TIKPAN_ADMIN_TOKEN` is set, every `/admin/*` request must include:

```text
Authorization: Bearer replace-with-a-long-random-admin-token
```

Frontend setup:

```bash
VITE_TIKPAN_API_URL=http://localhost:8787
VITE_TIKPAN_ADMIN_TOKEN=replace-with-a-long-random-admin-token
```

If you do not want to bake the token into `.env.local`, open the Supply Chain Admin page and use the `Admin access` card. It stores the token in this browser only as `localStorage.tikpan_admin_token`.

PowerShell admin request example:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8787/admin/tasks" `
  -Headers @{ Authorization = "Bearer replace-with-a-long-random-admin-token" }
```
