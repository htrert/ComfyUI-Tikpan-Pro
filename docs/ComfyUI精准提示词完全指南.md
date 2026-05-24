# ComfyUI 攀升AI节点 — 精准提示词完全指南

> 核心理念：**精准胜于堆砌。** 提示词不是越多越好，而是每个词都要有明确目的。

---

## 一、为什么"词堆得越多"反而越差？

很多新手写提示词喜欢堆砌：
```
❌ 反例
超高清，4K，8K，最高质量，完美，杰作，大师作品，
最好看的，非常漂亮，精细，photorealistic，hyperrealistic，
DSLR，bokeh，studio lighting，cinematic...（还有100个词）
```

**这样做的问题：**
1. 权重被稀释——每个词的影响力等比缩减
2. 词与词之间语义冲突（"柔和"和"硬朗"同时出现等于没说）
3. 占用有限的 token 配额，真正重要的描述被挤掉
4. AI 抓不住你真正想要的重点

**正确思路：**

> 3-5个关键描述词 × 精准 = 远胜 20个泛泛之词

---

## 二、提示词的4个维度框架

每条提示词按以下4个维度思考，不需要每个都填满：

```
[主体描述] + [场景/背景] + [风格/光效] + [技术参数]
```

| 维度 | 回答的问题 | 示例 |
|---|---|---|
| 主体描述 | 画面里最重要的是什么？ | 一瓶透明香水瓶，贴有白色标签 |
| 场景/背景 | 它在哪里？周围有什么？ | 置于黑色大理石台面，浅雾背景 |
| 风格/光效 | 整体感觉是什么？ | 高端商业摄影，暖色侧光，丁达尔光效 |
| 技术参数 | 画质/构图要求 | 竖版1:1，焦点清晰，背景虚化 |

---

## 三、场景化精准提示词模板

### 场景 1：商品图生成（电商/广告）

**目标：** 生成高端商业感产品图，保留产品细节，更换背景。

**最小有效提示词结构：**

```
[产品名称]，[产品特征关键词]，
placed on [背景描述]，
[光效描述]，
commercial photography，8K
```

**实战示例：**

```
✅ 好的提示词（18个词）：
A transparent glass perfume bottle with white label,
placed on wet black volcanic rock,
soft morning light, shallow depth of field,
luxury commercial photography

❌ 差的提示词（50+词）：
ultra detailed, hyperrealistic, 8K, 4K resolution, perfect quality,
masterpiece, best quality, beautiful perfume bottle, transparent glass,
stunning, perfect lighting, professional photography, award winning,
studio lighting, bokeh, sharp focus, high resolution...
```

**正向 vs 负向提示词分工：**

```
正向（告诉AI要什么）：
"A luxury skincare product on marble surface, golden hour sunlight"

负向（告诉AI不要什么）：
"text, watermark, logo, blurry, deformed, ugly background"
```

---

### 场景 2：人物/角色一致性生成

**核心难点：** 如何在多次生成中保持角色一致。

**特征描述公式：**

```
[性别+年龄段] + [发型颜色] + [眼睛颜色] + [独特特征] + [服装关键词]
```

**示例：**

```
✅ 精准角色描述（避免歧义词）：
28-year-old East Asian woman,
straight black hair to shoulders,
bright almond-shaped eyes,
wearing white lab coat,
confident expression
```

**避开的陷阱：**

```
❌ 不要用含糊的词：
"beautiful woman" → 无法控制具体样貌
"young person" → 年龄歧义
"nice clothing" → 服装无法复现

✅ 要用具体的词：
"27-year-old Chinese woman" → 确定年龄和民族特征
"short-cut auburn hair" → 颜色+长度+剪法
"navy blazer with gold buttons" → 颜色+款式+细节
```

---

### 场景 3：视频提示词（图生视频）

**视频提示词与图片最大的不同：描述动态，不描述静态。**

**框架：**

```
[主体状态] + [运镜方式] + [环境变化] + [锁定不变的要素]
```

**运镜关键词库：**

| 中文意图 | 英文关键词 |
|---|---|
| 镜头缓慢推进 | slow zoom in, camera slowly pushes forward |
| 镜头由远及近 | pull-in shot, dolly in |
| 环绕拍摄 | orbit shot, circular camera movement |
| 镜头上摇 | tilt up, upward pan |
| 抖动感 | handheld camera motion, slight shake |
| 定机拍摄 | static shot, locked-off camera |

**示例：**

```
✅ 视频提示词：
Camera slowly pushes forward toward the perfume bottle,
subtle water vapor rises around the bottle,
warm amber lighting gradually brightens,
product remains perfectly still and unchanged,
cinematic commercial style, 4K

❌ 避免这样写（描述静态画面）：
"beautiful perfume bottle on marble, nice lighting"
→ 这是图片描述，不会让视频动起来
```

---

### 场景 4：TTS 旁白文案（语音提示词）

**语气控制公式（发给 TTS 节点的提示词）：**

```
[语气风格关键词] + [语速指示] + [情感基调]
```

**示例：**

```
✅ 豆包/MiniMax TTS 语气指令：
"专业播音腔，语速适中，语调平稳有力，适合产品介绍"

✅ Gemini TTS 语气指令（英文）：
"Confident and warm narrator voice, 
slightly slow pace, suitable for luxury product advertisement"
```

**停顿控制（MiniMax/豆包支持）：**

```
欢迎来到今天的分享<#0.5#>
让我们一起了解这款产品<#0.3#>
它不只是一瓶香水<#0.8#>
更是一种生活方式
```

---

### 场景 5：Suno 音乐创作提示词

**精准音乐描述公式：**

```
[情感/用途] + [曲风] + [节奏感描述] + [乐器/音色关键词] + [时长/结构]
```

**示例：**

```
✅ 精准 Suno 提示词：
Upbeat Chinese commercial pop song for skincare product,
BPM around 120, bright and energetic,
female vocal, electronic synth bass,
catchy chorus hook, 30 seconds

风格标签：mandopop, electronic, commercial, upbeat
```

**常用风格标签（复制粘贴）：**

```
国风流行：mandopop, chinese pop, guqin elements
品牌广告：commercial, professional, uplifting, brand identity
短视频：viral, hook-driven, trendy, loopable
情感类：emotional, touching, slow ballad, acoustic
节日/活动：festive, celebratory, energetic, grand
```

---

## 四、AI 辅助写提示词（让 AI 帮你写提示词）

**核心思路：** 用 Gemini 3 Flash 或 GPT-5.4 Mini 分析参考图片，自动反推提示词。

### 方法一：参考图反推提示词

在 ComfyUI 中：

```
[LoadImage: 你喜欢的参考图] → [Gemini 3 Flash 分析]
  分析任务：画面提示词反推
  输出格式：提示词优化
  分析要求：提取可用于图像生成的精准英文提示词，
            按主体/场景/风格/技术参数分别列出，
            每个维度不超过5个词
```

**输出示例：**
```
主体：transparent amber glass bottle, embossed label
场景：white marble surface, scattered rose petals
风格：luxury commercial photography, warm golden light
技术：f/2.8 bokeh background, high contrast, editorial style
```

### 方法二：让 AI 帮你优化已有提示词

```python
# 在 GPT-5.4 Mini 节点中使用此系统指令：
你是专业的 AI 图像/视频生成提示词专家。
当用户给你一段描述后，你需要：
1. 提取核心意图（3句以内描述）
2. 生成精准的英文正向提示词（不超过 50 词）
3. 生成精准的负向提示词（不超过 20 词）
4. 说明每个关键词的作用

要求：
- 不要堆砌无意义的质量词（如 masterpiece, best quality）
- 每个词必须有明确的指向性
- 优先使用技术性描述词而非情感词
```

### 方法三：视频提示词生成链路（推荐工作流）

```
爆款视频
  ↓
[Gemini 3 Flash 分析 → 视频分镜拆解]
  ↓
[Grok 多图剧本重构]
  → 填入：你的产品描述 + 微调要求
  ↓
生成可直接使用的视频提示词
```

---

## 五、分场景提示词参数设置建议

### 图片生成参数对照表

| 场景 | 分辨率 | 比例 | 画质 | 参考图数量 |
|---|---|---|---|---|
| 电商主图 | 2K | 1:1 | high | 1（产品图） |
| 竖版海报 | 2K | 9:16 | high | 1-2 |
| 人物生成 | 2K | 3:4 | high | 2-3（角色参考） |
| 场景概念图 | 1K | 16:9 | medium | 1（风格参考） |
| 快速测试 | 1K | 1:1 | low | 0 |

### 视频生成参数建议

| 场景 | 时长 | 分辨率 | mode |
|---|---|---|---|
| 商品展示 | 8-10s | 1080p | 异步 |
| 广告素材 | 15s | 1080p | 异步 |
| 测试效果 | 5s | 720p | 同步 |
| 人物动态 | 8s | 1080p | 异步 |

---

## 六、负向提示词精简原则

**原则：负向提示词只写会出现且你不想要的**

```
❌ 堆砌式负向提示词（无效）：
ugly, bad, worst, low quality, blurry, deformed, mutation,
extra limbs, missing limbs, disconnected limbs...（50个词）

✅ 针对性负向提示词（有效）：
# 商品图：
text, watermark, multiple products, floating, shadow artifacts

# 人物图：
extra fingers, distorted face, asymmetric eyes

# 视频：
shaky footage, color banding, artifacts
```

**黄金原则：**
- 看一次生成结果，发现有什么问题，把那个具体问题加进负向提示词
- 不要提前堆砌你还没遇到的问题

---

## 七、实战案例：从零写一套电商商品图提示词

**场景：** 一款国风茶叶包装礼盒，要生成4张不同场景的商品图

**步骤1：确定主体特征（5个词以内）**
```
Chinese tea gift box, red lacquer finish, gold phoenix embossing
```

**步骤2：4个不同场景（每个场景只换背景部分）**

```
场景1（高端商务）：
主体: Chinese tea gift box, red lacquer, gold phoenix embossing
背景: dark mahogany desk, inkstone nearby, soft side lighting
风格: luxury product photography, 8K commercial

场景2（自然茶园）：
主体: Chinese tea gift box, red lacquer, gold phoenix embossing
背景: misty bamboo forest ground, fallen leaves
风格: natural atmospheric, diffused morning light

场景3（简约极简）：
主体: Chinese tea gift box, red lacquer, gold phoenix embossing
背景: light beige gradient background, no shadow
风格: minimalist studio photography, clean

场景4（礼品场景）：
主体: Chinese tea gift box, red lacquer, gold phoenix embossing
背景: red envelope and chrysanthemums arrangement on silk fabric
风格: festive Chinese new year commercial photography
```

**负向提示词（4张共用）：**
```
text overlay, watermark, blurry box, multiple boxes,
distorted proportions, artificial looking background
```

---

## 八、提示词管理建议

1. **建立个人提示词库**：把验证过的提示词保存在文本文件里，按场景分类
2. **记录参数组合**：效果好的提示词+参数（分辨率/比例/种子）一起保存
3. **善用 seed 复现**：找到好效果后固定 seed，批量生成变体时改其他参数
4. **渐进调整**：一次只改一个变量，方便判断是什么起作用了
5. **低档位测试**：1K 分辨率确认构图和内容，满意后再升到 2K/4K
