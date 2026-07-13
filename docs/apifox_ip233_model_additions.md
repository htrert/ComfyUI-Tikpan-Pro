# Apifox 新增模型 API 草稿（隐藏上游域名）

> Apifox 里请使用环境变量 `{{baseUrl}}`，不要在公开文档正文写上游域名。实际接口根地址只放在私有环境配置中。

## 通用鉴权

- Header: `Authorization: Bearer {{apiKey}}`
- Header: `Content-Type: application/json`

## GPT-Image-2-C 旧版兼容生图

- 名称：创建图片 gpt-image-2-c
- 方法：`POST`
- 路径：`/v1/images/generations`
- 说明：旧版 `gpt-image-2-all` 节点恢复版，模型名改为 `gpt-image-2-c`。

```json
{
  "model": "gpt-image-2-c",
  "prompt": "电影感城市夜景",
  "size": "1024x1024",
  "n": 1
}
```

## GPT-Image-2-C 旧版兼容修图

- 名称：编辑图片 gpt-image-2-c
- 方法：`POST`
- 路径：`/v1/chat/completions`
- 说明：旧版修图节点恢复版，底图/参考图用 `image_url` data URI 传入消息内容。

```json
{
  "model": "gpt-image-2-c",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "把背景换成海边，主体保持一致"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,{{base64Image}}"}}
      ]
    }
  ],
  "size": "1024x1024",
  "quality": "hd"
}
```

## Grok Video

- 名称：创建视频 grok-video
- 方法：`POST`
- 路径：`/v1/video/generations`
- 说明：支持文生、单图/多参考图生视频；多参考图时 `seconds` 建议不超过 10。

```json
{
  "model": "grok-video",
  "prompt": "A cinematic shot of a red sports car driving through rainy neon streets at night",
  "seconds": 6,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "image_urls": ["https://example.com/reference.png"]
}
```

## Grok Video 1.5

- 名称：创建视频 grok-video-1.5
- 方法：`POST`
- 路径：`/v1/video/generations`
- 说明：必须且只能 1 张参考图；支持 `16:9` / `9:16`，`480p` / `720p`。

```json
{
  "model": "grok-video-1.5",
  "prompt": "Gentle camera push-in, water flowing",
  "seconds": 4,
  "resolution": "720p",
  "aspect_ratio": "16:9",
  "image_urls": ["https://example.com/product.png"]
}
```

## 查询视频任务

- 名称：查询视频生成结果
- 方法：`GET`
- 路径：`/v1/video/generations/{task_id}`

## Seedance 2.0 系列

- 名称：创建视频 Seedance 2.0
- 方法：`POST`
- 路径：`/v1/videos`
- 模型：`Seedance-2.0`、`seedance-2.0-mini-480p`、`seedance-2.0-mini-720p`、`seedance-2.0-fast-480p`、`seedance-2.0-fast-720p`、`seedance-2.0-480p`、`seedance-2.0-720p`、`seedance-2.0-1080p`、`seedance-2.0-4k`

```json
{
  "model": "seedance-2.0-720p",
  "prompt": "A cinematic short video with smooth motion and realistic lighting",
  "duration": 6,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "image_url": "https://example.com/reference.png",
  "reference_image_urls": ["https://example.com/reference.png"]
}
```

## Veo 3.1 系列

- 名称：创建视频 veo-3-1 / veo-3-1-fast
- 方法：`POST`
- 路径：`/v1/videos`
- 模型：`veo-3-1`、`veo-3-1-fast`

```json
{
  "model": "veo-3-1-fast",
  "prompt": "A drone shot over a futuristic coastal city",
  "duration": 8,
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "generate_audio": true,
  "reference_mode": "frame",
  "images": ["https://example.com/reference.png"]
}
```

## Omni 系列

- 名称：创建视频 omni-fast / omni-fast-no-water
- 方法：`POST`
- 路径：`/v1/videos`
- 模型：`omni-fast`、`omni-fast-no-water`

```json
{
  "model": "omni-fast",
  "prompt": "Animate the scene with natural subject motion",
  "aspect_ratio": "16:9",
  "image_url": "https://example.com/reference.png"
}
```

## Omni V2V 系列

- 名称：视频转视频 omni-v2v / omni-v2v-no-water
- 方法：`POST`
- 路径：`/v1/videos`
- 模型：`omni-v2v`、`omni-v2v-no-water`

```json
{
  "model": "omni-v2v",
  "prompt": "Restyle this video into a cinematic night scene",
  "video_url": "https://example.com/source.mp4",
  "aspect_ratio": "16:9"
}
```

## 查询 OpenAI 视频任务

- 名称：查询 `/v1/videos` 视频任务
- 方法：`GET`
- 路径：`/v1/videos/{id}`
