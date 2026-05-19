# Tikpan Async Engine 无限画布式并行说明

这个方案的目标是：在一个 ComfyUI 工作流里，让多个 API 任务像无限画布里的卡片一样先独立启动、后台运行，再统一查询结果。

它不强行修改 ComfyUI 主队列，而是把长耗时 API 请求放进 Tikpan 后台任务池。ComfyUI 节点只负责提交任务和查询任务。

## 新增节点

### Tikpan Async: Submit Image Task

提交一个图片生成任务，马上返回：

```text
Task_ID
Stage_Log
Task_JSON
```

这个节点不会等图片生成完成，所以多个 Submit 节点可以很快把任务都提交到后台。

### Tikpan Async: Query Image Result

查询一个任务。

`Wait_Mode = return_now` 时立即返回当前状态。

`Wait_Mode = wait_until_done` 时等待到成功、失败或超时。

### Tikpan Async: Join Image Tasks

接收最多 8 个 `Task_ID`，统一等待多个任务完成，把成功的图片合并成一个 batch 输出。

这是最接近无限画布并行体验的节点。

### Tikpan Async: Recent Tasks

查看当前 ComfyUI 进程里的最近任务列表。

## 推荐工作流

### 多个任务真正先启动

1. 放多个 `Tikpan Async: Submit Image Task`。
2. 每个 Submit 节点填不同模型、不同提示词或不同供应商。
3. 把每个 Submit 的 `Task_ID` 接到 `Tikpan Async: Join Image Tasks`。
4. Join 节点设置：

```text
Wait_All = true
Max_Wait_Seconds = 900
Poll_Interval_Seconds = 3
```

5. 把 Join 的 `Images` 接到 `Preview Image` 或 `Save Image`。

这样 ComfyUI 会先执行所有 Submit 节点。Submit 节点很快返回后，后台任务池已经开始并行跑。最后 Join 节点统一等待和收图。

## 为什么比普通节点更像无限画布

普通 ComfyUI 节点通常是：

```text
节点开始 -> 等 API 完成 -> 输出结果 -> 下一个节点
```

Async Engine 是：

```text
Submit 节点 -> 返回 task_id -> 后台继续跑
Join 节点 -> 按 task_id 等结果 -> 汇总图片
```

也就是把耗时部分从 ComfyUI 节点执行线程里拆出去了。

## 结果保存在哪里

图片和任务 JSON 会保存到：

```text
ComfyUI/output/TikpanAsync
```

任务 JSON 包含：

```text
task_id
status
stage
progress
events
image_paths
error
```

## 状态阶段

任务阶段按照你的商业网站逻辑拆成：

```text
server -> upstream -> oss -> cdn
```

在 ComfyUI 本地版里：

`oss` 表示图片已保存到本地输出目录。

`cdn` 表示结果已准备给 Query / Join 节点读取。

后续接网站时，可以把 `oss` 换成真实对象存储上传，把 `cdn` 换成真实 CDN 地址回写。

## 重要边界

这个版本已经实现“API 后台并行”，但还没有修改 ComfyUI 的本地 GPU 执行器。

也就是说：

本地 GPU 节点仍然受 ComfyUI 主队列控制。

Tikpan API 任务可以通过后台任务池并行运行。

下一步如果要做到“本地 GPU 节点、API 节点、网站任务全部统一调度”，需要把这个后台任务池升级成独立服务，并给 ComfyUI、网站、无限画布共同接入同一套任务 API。
