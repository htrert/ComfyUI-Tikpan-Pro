# Tikpan Parallel Engine ComfyUI 使用说明

> 路径：`👑 Tikpan 官方独家节点 / 06 任务与并发 Tools / 并发引擎 Parallel Engine`

这个节点是 Tikpan Pro 的 API 并发生图引擎第一版。它不修改 ComfyUI 全局队列，而是在单个节点内部管理多个 API 请求，所以适合稳定地做模型对比、Tikpan 通道容灾和批量出图。

## 节点在哪里

重启 ComfyUI 后，在节点搜索里输入：

```text
Tikpan API 多模型并发生图引擎
```

节点类名：

```text
TikpanParallelImageEngineNode
```

## 基本用法

1. 添加节点 `Tikpan：API 多模型并发生图引擎`。
2. 填写 `API_Key`，例如 `sk-...`。
3. 在 `Prompt` 写生成提示词。
4. 在 `Models` 里一行一个模型。
5. `Relay_Hosts` 默认只使用 Tikpan 官方中转站。
6. 日常商用建议 `Strategy = failover`。
7. 输出 `Images` 接到 `Preview Image` 或 `Save Image`。

示例：

```text
Models:
grok-imagine-image
grok-imagine-image-pro

Relay_Hosts:
https://tikpan.com
```

## 三种策略

`failover`

默认推荐。按顺序一个一个尝试，成功就停止。最省钱，适合日常商用。

例如 2 个模型、2 个供应商，最多会尝试 4 次，但只要第 1 次成功，就只发第 1 次请求。

`race_first_success`

同时发出多个请求，谁先成功就先返回。适合抢速度，但已经发出去的慢请求也可能继续被上游处理，所以可能多扣余额。

`parallel_all`

所有模型组合全部跑完，成功图片合并成一个 batch。适合比较效果、压测 Tikpan 通道、批量出图，但会按发出的请求正常消耗余额。

## 输出说明

`Images`

ComfyUI 图片 batch，可以接 `Preview Image`、`Save Image` 或后续图片节点。

`Stage_Log`

阶段日志，按商业链路拆成：

```text
user -> server -> upstream -> oss -> cdn
```

如果失败，会显示失败环节。例如供应商返回错误，就是 `upstream/error`。

`Result_JSON`

每个模型、每个 Tikpan 请求的详细结果，适合排查哪个通道失败。

## 推荐参数

日常省钱：

```text
Strategy = failover
Max_Concurrency = 1
Images_Per_Model = 1
```

抢最快结果：

```text
Strategy = race_first_success
Max_Concurrency = 3
Images_Per_Model = 1
```

批量对比：

```text
Strategy = parallel_all
Max_Concurrency = 4
Images_Per_Model = 1
```

## 当前中转站策略

当前版本已固定只使用：

```text
https://tikpan.com
```

即使旧工作流里残留其他中转站地址，节点也会自动回退到 `https://tikpan.com`。后续如果重新开放多供应商，需要先改 `nodes/tikpan_node_options.py` 里的 `API_HOST_OPTIONS`。

## 关于多个节点独立运行

这个节点解决的是“一个节点内部多个 API 任务”的并发。

你想要的“一个 ComfyUI 工作流里多个节点像无限画布一样独立运行、互不影响”，需要下一层架构：独立任务调度服务 + ComfyUI 节点提交任务 + 后台并行执行 + 节点按任务 ID 查询结果。

普通 ComfyUI 工作流默认仍然受主队列和依赖图控制。要做到真正独立运行，不能只写一个节点，需要把长任务从 ComfyUI 主执行线程里拆出去。
