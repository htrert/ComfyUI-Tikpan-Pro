# 沧元算力单模型接入实操

当前第一阶段只接一个真实模型：

```text
Tikpan 前台分类：图片模型
Tikpan 平台模型：tikpan.image.gpt-image-2-4k
沧元展示模型：gpt-image-2-4k
沧元上游模型 ID：cy-img2-gpt-image-2-4k
提交接口：POST https://ai.cangyuansuanli.cn/v1/images/generations
轮询接口：GET  https://ai.cangyuansuanli.cn/v1/images/generations/{task_id}
```

## 1. 为什么要这样配

前台只负责展示：

- 图片模型
- 视频模型
- 模型名称
- 模型支持的参数
- 预估 Tokens

后台负责配置：

- 分类
- 平台模型
- 上游供应商
- 上游模型真实 ID
- 每个上游模型支持的参数
- 平台参数到上游参数的映射
- 多渠道优先级、权重、成本、售价

这样后续你接第二家、第三家中转站时，即使同一个模型参数支持不同，也可以通过 `model_channels` 和 `channel_parameter_mappings` 分别处理。

## 2. 沧元后台准备

在浏览器已打开的沧元算力页面：

1. 进入 `控制台`
2. 找到 `API 密钥` 或 `Token`
3. 新建一个 Key，复制一次即可
4. 进入 `模型广场`
5. 打开 `gpt-image-2-4k` 的 `查看文档`
6. 确认模型 ID、接口和参数是否仍和本文件一致

不要把 Key 写进代码仓库。

## 3. 本地环境变量

PowerShell 示例：

```powershell
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro\landing-page\api

$env:TIKPAN_PROVIDER_ADAPTER='http'
$env:TIKPAN_PROVIDER_SECRETS='{"cangyuan":"sk-你的沧元令牌"}'
```

如果你复制 `.env.example`，也可以把对应值写进本地 `.env`，但不要提交真实 Key。

## 4. PostgreSQL 模式

执行已有迁移后，再执行：

```text
api/db/migrations/008_seed_cangyuan_gpt_image_2_4k.sql
```

这个 seed 会创建：

- `providers`: `cangyuan`
- `platform_models`: `tikpan.image.gpt-image-2-4k`
- `provider_models`: `pm-cangyuan-gpt-image-2-4k`
- `model_channels`: `ch-cangyuan-gpt-image-2-4k`
- 参数映射：`prompt`、`size`、`n`、`quality`、`background`、`output_format`、`output_compression`、`moderation`、`stream`、`partial_images`、`async`

## 5. Memory 模式

Memory 模式不会自动执行 SQL。你可以先用后台 API 配置同样内容；如果设置了 `TIKPAN_ADMIN_TOKEN`，请求要加后台 Authorization。

建议后续把后台页面做成可视化配置表单，目前先用 SQL/PostgreSQL 更稳。

## 6. 参数设计原则

平台模型 schema 是前台表单来源。

渠道参数映射是实际传给上游的来源。

例如：

```text
平台参数 prompt -> 沧元 prompt
平台参数 size -> 沧元 size
平台参数 async -> 沧元 async，默认 true
平台参数 background -> 沧元 background，默认 opaque
```

如果另一家上游不支持 `background`，不要删平台参数，只要给那条渠道配置：

```text
background -> omit
```

如果另一家上游把 `size` 叫 `image_size`，那条渠道配置：

```text
size -> image_size
```

如果另一家上游的尺寸枚举不同，那条渠道配置：

```text
size -> image_size
transform = map
value_map = {"1024x1024":"square","1536x1024":"landscape"}
```

这就是为什么参数不能写死在前台组件里。

## 7. 运行检查

```powershell
npm run check
```

真实调用前，确认：

- `TIKPAN_PROVIDER_ADAPTER=http`
- `TIKPAN_PROVIDER_SECRETS` 里有 `cangyuan`
- 沧元 Key 可用且余额充足
- `upstream_model_name` 与沧元模型广场保持一致

## 8. 关于异步图片

`gpt-image-2-4k` 是异步图片任务。

Tikpan HTTP provider adapter 已支持在 `provider_models.raw_capabilities` 里配置：

```json
{
  "endpoint_path": "/v1/images/generations",
  "async_poll": true,
  "poll_status_path": "/v1/images/generations/{task_id}",
  "poll_interval_ms": 1500
}
```

提交后会自动轮询结果，直到返回完成状态或结果 URL。
