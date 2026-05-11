# Canvas Model Studio

一个面向未来云端模型网站的无限画布 MVP。当前可以连接本地 ComfyUI，后续可以切换为由网站直接向上游模型服务发送请求。

## 产品思路

ComfyUI 节点本质上是在把模型、prompt、采样器、尺寸、seed、ControlNet 等参数打包成一次生成请求。这个项目把这些已经验证过的参数保存在“参数档案”里：

- 本地开发阶段：网站把参数档案转换成 ComfyUI workflow，提交到本机 ComfyUI。
- 云端产品阶段：网站把同一份参数档案转换成统一 JSON 请求，发送到 `UPSTREAM_URL`。
- 用户侧体验：用户只看到无限画布、prompt、图片和简单控件，不需要下载 ComfyUI。

## 启动本地 ComfyUI 模式

先启动 ComfyUI，默认地址是 `http://127.0.0.1:8188`，然后运行：

```powershell
$env:TIKPAN_API_KEY="sk-你的Tikpan或NewAPI密钥"
node server.js
```

打开：

```text
http://127.0.0.1:3456
```

如果 ComfyUI 不在默认地址：

```powershell
$env:COMFY_URL="http://127.0.0.1:8188"; node server.js
```

### 本地 ComfyUI + Tikpan 节点

当前画布已经内置这些 Tikpan 节点档案：

- GPT Image 2 官方生图：`TikpanGptImage2OfficialNode`
- Nano Banana Pro / Gemini 图片：`TikpanNanoBananaProNode`
- 豆包 Seedream 5.0：`TikpanDoubaoImageNode`
- GPT Image 2 图片编辑：`TikpanGptImage2OfficialEditV2`
- Veo 3.1 视频：`TikpanVeoVideoNode`
- Grok 视频：`TikpanExclusiveVideoNode`
- Suno 音乐：`TikpanSunoMusicNode`

配置要点：

```powershell
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro\experiments\canvas_model_studio
$env:COMFY_URL="http://127.0.0.1:8188"
$env:TIKPAN_API_KEY="sk-你的上游密钥"
node server.js
```

选择 Tikpan 节点档案后，点击“预览请求”可以看到实际提交给 ComfyUI 的 workflow。图片编辑类档案需要先选中画布上的图片节点；多参考图类档案会按画布图片顺序传给节点。

## 接入正式网站用户系统

画布可以复用 `web_app` 的登录、余额和用户信息接口。先启动正式网站：

```powershell
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro\web_app
python app.py
```

再启动画布：

```powershell
cd D:\ComfyUI-aki-v2\ComfyUI\custom_nodes\ComfyUI-Tikpan-Pro\experiments\canvas_model_studio
$env:WEB_APP_URL="http://127.0.0.1:5000"
$env:REQUIRE_LOGIN="true"
$env:TIKPAN_API_KEY="sk-你的上游密钥"
node server.js
```

- `WEB_APP_URL`：让画布通过正式网站的 `/api/login`、`/api/register`、`/api/user/info` 做用户态桥接。
- `REQUIRE_LOGIN=true`：要求登录后才能生成和保存项目。
- 项目文件会按用户隔离保存到 `data/projects/<user-id>/`。

## 启动云端上游模式

上游服务需要提供 `POST /generate`，返回：

```json
{
  "requestId": "job-id",
  "images": [
    { "url": "https://example.com/output.png" }
  ],
  "seed": 123
}
```

启动方式：

```powershell
$env:PROVIDER="upstream"
$env:UPSTREAM_URL="https://your-model-api.example.com"
$env:UPSTREAM_TOKEN="optional-token"
node server.js
```

生产环境建议让 `UPSTREAM_URL` 指向正式 `web_app` 或单独的模型网关，由它负责扣费、路由、失败退款和日志。

## 当前功能

- 无限画布：拖拽平移、滚轮缩放、节点移动。
- Prompt 卡片：双击空白处或点击按钮添加。
- 图片导入：导入本地图片并放到画布。
- 参数档案：保存你在 ComfyUI 里验证过的 checkpoint、尺寸、采样器、步数、CFG 等。
- 请求预览：查看网站将发送的统一请求，以及本地 ComfyUI workflow。
- 生成回贴：生成结果会作为图片节点贴到当前选中节点右侧。
- 项目保存：保存为 `data/projects/<项目名>.json`。

## 关键文件

- `server.js`：本地 Web 服务、ComfyUI provider、云端 upstream provider。
- `data/model-profiles.json`：模型参数档案。
- `public/index.html`：网站页面。
- `public/app.js`：画布交互和请求逻辑。
- `public/styles.css`：界面样式。
## AI 内容工厂工作流

现在左侧已经加入“内容工厂”面板，可选择：

- AI短剧 / 漫剧工厂
- 小说推文 / TikTok 切片
- TikTok 电商内容工厂

输入小说片段、短剧梗概、产品信息或账号定位后，点击“生成内容工厂画布”，系统会自动铺开项目 Brief、角色/场景资产、九宫格分镜、生成任务、音乐/后期和发布清单节点。

完整业务逻辑、后端表结构和开发优先级见 `CONTENT_FACTORY_WORKFLOW.md`。
