# Tikpan AI Director — 设计规划文档

> 比 BigBanana 更强：全模型捆绑攀升AI + 更丰富的剧集工作流

---

## 一、产品定位

**Tikpan AI Director** 是基于攀升AI中转站的工业级 AI 短剧/漫剧创作平台。

与 BigBanana 的核心区别：
- BigBanana：依赖 AntSK 单一平台，后端闭源
- Tikpan AI Director：完全开放源码，所有 AI 模型通过攀升AI中转，支持图片+视频+音频完整工作流

---

## 二、核心工作流

```
输入：一句话 / 小说片段 / 故事梗概
        ↓ [LLM 剧本创作]
    多集剧本（集 × 分镜）
        ↓ [角色/场景资源库]
    人物参考图 + 场景风格设定
        ↓ [GPT-Image-2 / Gemini 多参考图]
    分镜插图（角色一致性保持）
        ↓ [HappyHorse I2V / Veo / Vidu3]
    分镜视频片段（可选）
        ↓ [豆包TTS / MiniMax speech]
    配音旁白
        ↓ [Suno 音乐]
    背景音乐
        ↓ [FFmpeg 合成]
    成片（MP4）
```

---

## 三、技术架构

```
tikpan-director/
├── backend/                    # Python Flask API
│   ├── app.py                  # 入口
│   ├── api/
│   │   ├── project.py          # 项目/集管理
│   │   ├── asset.py            # 角色/场景/道具资源
│   │   ├── storyboard.py       # 分镜生成
│   │   ├── render.py           # 图片/视频/音频渲染
│   │   └── export.py           # 导出成片
│   ├── services/
│   │   ├── llm.py              # 剧本生成（Gemini 3.5 Flash）
│   │   ├── image.py            # 图片生成（复用 tikpan nodes）
│   │   ├── video.py            # 视频生成（异步队列）
│   │   ├── audio.py            # 配音+音乐
│   │   └── consistency.py      # 角色一致性管理
│   └── models/
│       ├── project.py          # 项目 ORM
│       ├── storyboard.py       # 分镜 ORM
│       └── asset.py            # 资源 ORM
│
├── frontend/                   # Vue 3 + Vite
│   ├── src/
│   │   ├── views/
│   │   │   ├── Projects.vue    # 项目列表
│   │   │   ├── Editor.vue      # 剧集编辑器（主界面）
│   │   │   ├── Assets.vue      # 资源库
│   │   │   └── Export.vue      # 导出中心
│   │   ├── components/
│   │   │   ├── StoryCard.vue   # 分镜卡片
│   │   │   ├── CharPanel.vue   # 角色面板
│   │   │   └── Timeline.vue    # 时间轴视图
│   │   └── stores/
│   │       ├── project.ts
│   │       └── render.ts
│   └── vite.config.ts
│
├── docker-compose.yml          # 一键部署
├── .env.example                # 环境变量模板
└── README.md
```

---

## 四、数据库设计

```sql
-- 项目
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    genre TEXT DEFAULT 'comic',   -- comic/drama/anime
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 角色（资源库）
CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,           -- 形象描述（用于提示词）
    reference_image_url TEXT,   -- 参考图URL
    prompt_tags TEXT,           -- 角色一致性提示词片段
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 场景（资源库）
CREATE TABLE scenes (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    style_image_url TEXT,
    prompt_tags TEXT
);

-- 集
CREATE TABLE episodes (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    title TEXT,
    synopsis TEXT,
    script TEXT,               -- 完整剧本文本
    status TEXT DEFAULT 'draft'
);

-- 分镜
CREATE TABLE storyboards (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    scene_description TEXT,   -- 画面描述
    dialogue TEXT,            -- 台词
    character_ids TEXT,       -- JSON 数组，引用哪些角色
    scene_id INTEGER,
    shot_type TEXT,           -- 景别：close/medium/wide
    camera_move TEXT,         -- 运镜
    image_prompt TEXT,        -- 最终图片提示词（AI优化后）
    image_url TEXT,           -- 生成的图片
    video_url TEXT,           -- 生成的视频片段（可选）
    audio_url TEXT,           -- 配音音频
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

-- 渲染任务队列
CREATE TABLE render_tasks (
    id INTEGER PRIMARY KEY,
    storyboard_id INTEGER,
    task_type TEXT,          -- image/video/audio/export
    task_id TEXT,            -- 上游 task_id（异步）
    status TEXT DEFAULT 'pending',
    model_id TEXT,
    credits_used INTEGER DEFAULT 0,
    result_url TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、核心 API 端点规划

```
POST   /api/projects                  # 创建项目
GET    /api/projects                  # 项目列表
GET    /api/projects/:id              # 项目详情

POST   /api/projects/:id/episodes     # 创建集
POST   /api/episodes/:id/generate-script    # AI生成剧本
POST   /api/episodes/:id/generate-storyboard # AI生成分镜

POST   /api/assets/characters         # 添加角色（上传参考图）
POST   /api/assets/scenes             # 添加场景

POST   /api/storyboards/:id/render-image    # 渲染分镜图片
POST   /api/storyboards/:id/render-video    # 渲染视频（可选）
POST   /api/storyboards/:id/render-audio    # 渲染配音

GET    /api/render-tasks/:task_id     # 查询渲染任务状态

POST   /api/episodes/:id/export       # 导出整集视频
GET    /api/episodes/:id/export-status # 导出进度
```

---

## 六、攀升AI模型映射

| 工作流步骤 | 推荐模型 | 端点 |
|---|---|---|
| 剧本生成 | Gemini 3.5 Flash | tikpan.com /v1beta |
| 分镜提示词优化 | GPT-5.4 Mini | tikpan.com /v1/responses |
| 角色一致性图片 | GPT-Image-2-all（多参考图） | tikpan.com /v1/images/generations |
| 场景图片 | Gemini 14图极限生图 | tikpan.com /v1/images/generations |
| 图生视频（可选） | HappyHorse I2V | tikpan.com |
| 配音 | 豆包TTS 2.0 | tikpan.com /api/v3/tts |
| 背景音乐 | Suno V5 | tikpan.com /suno |

---

## 七、与 BigBanana 的差异优势

| 维度 | BigBanana | Tikpan AI Director |
|---|---|---|
| 模型来源 | 单一 AntSK 平台 | 攀升AI全部模型 |
| 视频支持 | 有限 | HappyHorse/Veo/Vidu3 全接入 |
| 音频支持 | 无 | TTS + Suno 音乐 |
| 源码 | 闭源（仅Docker镜像） | 完全开源 |
| 部署方式 | Docker only | Docker + 本地 Python |
| 扩展性 | 依赖上游 | 自定义扩展任意模型 |
| 角色一致性 | 基础 | 多参考图 + 提示词锁定 |
| 商业化 | 需授权 | MIT 开源 |

---

## 八、开发路线图

**v0.1（MVP，2周内）：**
- [ ] 项目/集/分镜 CRUD
- [ ] 角色资源库（上传参考图）
- [ ] LLM 剧本 → 分镜拆解
- [ ] GPT-Image-2 多参考图分镜图片
- [ ] 配音（豆包TTS）

**v0.2（配音+音乐，+1周）：**
- [ ] Suno 背景音乐
- [ ] 分镜音频分配
- [ ] 基础导出（图片序列 + 配音）

**v0.3（视频，+2周）：**
- [ ] HappyHorse I2V 分镜视频
- [ ] 异步队列管理 UI
- [ ] FFmpeg 自动合成整集

**v1.0（完整商业版）：**
- [ ] 完整前端 UI（Vue 3）
- [ ] 用户账号系统（复用 web_app）
- [ ] 积分计费集成
- [ ] Docker 一键部署
