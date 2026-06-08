# PSD 智能分层使用指南（商业级管线）

> 节点名：**工具｜智能分层 PSD 生成器**
> 路径：`👑 Tikpan 官方独家节点 / 06 任务与并发 Tools / PSD Tools`

---

## 🎯 一句话定位

输入一张图，自动分离主体/装饰/文字/二维码等元素，输出 Photoshop 2023+ 可直接打开的分层 PSD。三档可选 + 6 种场景预设，覆盖电商/海报/人像/生活场景日常需求。

---

## 📦 三档选择

| 档位 | 核心算法 | 单张耗时（GPU） | 典型分层数 | 适用 |
|------|---------|-----------------|-----------|------|
| **经济档** | BiRefNet 抠图 + cv2 连通域 + PaddleOCR | 5-15 秒 | 5-10 | 简单商品图、追求速度 |
| **标准档**（推荐） | BiRefNet + SAM2 自动多尺度 + PaddleOCR | 20-60 秒 | 10-20 | 大多数日常场景 |
| **极致档** | BiRefNet + GroundingDINO 语义分割 + SAM2 多尺度补漏 + LaMa 补全 | 60-180 秒 | 20-50 | 商业级商品图、复杂海报 |

三档共用：
- **BiRefNet** 主体抠图（电商抠图当前 SOTA，发丝/边缘/反光强）
- **PaddleOCR 3.x** 中文识别（90%+ 准确率，远超 EasyOCR）
- 失败自动降级到 rembg / EasyOCR

只有极致档：
- **GroundingDINO** 文本提示驱动的语义分割（按 logo/badge/button/price tag 等语义独立成层）
- **LaMa Inpainting** 把元素遮挡的背景补全
- **品牌色块**（k-means 颜色聚类，海报场景启用）

---

## 🎨 场景预设（新增）

下拉框 6 选项，自动切换 GroundingDINO 提示词集和增强模块：

### 自动检测（默认推荐）
先用 GroundingDINO 粗识别人/商品/食物/家具/文字的占比，自动判断场景类型。`person>15%` 选人像；`food/furniture>10%` 选生活；`text>20% 且 product<30%` 选海报；其他选商品图。

### 电商商品图（白底/主图）
**专用提示词**：`product, logo, brand, price tag, sale sticker, discount badge, coupon, qr code, barcode, box, package, jar, bottle...`
**附加增强**：二维码/条形码自动识别独立成层（图层名带扫码内容预览：`qrcode_1_https://t.cn`）

### 电商详情页/海报/Banner
**专用提示词**：`title, headline, subtitle, cta button, ribbon, banner, frame, border, ornament, pattern...`
**附加增强**：
- 文字按字号自动分组成「标题/副标题/正文/价格/小字」5 类图层（含 `¥/$/元/折/off` 的自动拎到价格组）
- 极致档下用 k-means 提取 5 个主要品牌色块（图层名带 hex 颜色：`色块_#FF3344_1`）

### 人物/生活方式图
**专用提示词**：`person, face, hair, clothing, shoes, jewelry, accessory, bag...`
**附加增强**：自动切换 **BiRefNet-Portrait** 人物专用模型（专为人像 finetune，发丝/皮肤/边缘比通用版更准）

### 生活场景图（食物/家居）
**专用提示词**：`food, dish, plate, bowl, drink, plant, furniture, lamp, window, door...`

### 全场景（最多层）
所有词都进 prompt + 所有增强模块都开。出层最多但也最慢、最多误检，仅在对前几种都不满意时用。

---

## 🔌 节点输入参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| 输入图片 | IMAGE | - | 必填，要分层的图 |
| 文件名 | STRING | smart_layered | PSD 文件名（无后缀） |
| 分层档位 | 下拉 | 标准档 | 经济/标准/极致 |
| **场景类型** | 下拉 | 自动检测 | 新增，6 选项见上 |
| 补全被遮挡区域 | 是/否 | 否 | 标准档+此项=极致档效果 |
| 检测文字 | 是/否 | 是 | OCR 识别文字成层 |
| 最小元素面积 | INT | 2000 | 过滤小于此面积的元素（px²） |
| 边缘羽化 | INT | 5 | 边缘高斯模糊半径 |
| 自动安装依赖 | 是/否 | 是 | 首次会自动 pip 安装 |

### 输出

| 输出 | 类型 | 说明 |
|------|------|------|
| PSD 文件路径 | STRING | 完整磁盘路径 |
| 分层日志 | STRING | 用了哪些模型、分了几层、每层名字 |
| 预览图 | IMAGE | 缩略图墙，PS 之外快速预览 |

---

## 🏗️ 图层结构

输出 PSD 自动按以下 3 个组归类（PS 里展开能直接看到）：

```
PSD 文件
├── 原图_参考（reference，默认隐藏，方便对照）
├── 📁 背景层
│   └── 背景（去掉所有前景后的图，极致档已 LaMa 补全）
├── 📁 产品元素
│   ├── logo_左上_1               ← GroundingDINO 语义命名
│   ├── badge_中心_2
│   ├── 主产品_中心                ← 启发式命名（无语义时）
│   ├── qrcode_1_https://t.cn      ← 二维码层（电商场景）
│   ├── 色块_#FF3344_1             ← 品牌色块层（极致档+海报场景）
│   └── ...
└── 📁 文字层
    ├── 文字_标题_夏季_大促        ← 字号聚类（海报场景）
    ├── 文字_副标题_全场
    ├── 文字_价格_¥99              ← ¥/$/元 自动拎进价格组
    └── 文字_正文_包邮到家
```

---

## 🚀 快速开始

### 首次使用

1. 工作流加一个「**工具｜智能分层 PSD 生成器**」节点
2. 把生图/加载图节点的 IMAGE 输出连进去
3. 默认设置即可：标准档 + 自动检测
4. 执行节点
5. 首次会**自动下载模型**（一次性，~2-3 GB）：
   - BiRefNet ~900MB → `ComfyUI/models/birefnet/`
   - GroundingDINO ~700MB → `ComfyUI/models/grounding_dino/`
   - PaddleOCR ~200MB → 用户主目录
   - SAM2 ~180MB（如已有则跳过）
   - 选了"人物"场景额外下载 BiRefNet-Portrait ~900MB

### 日常使用

- **大多数情况**：标准档 + 自动检测，开 20-30 秒拿到 10-20 层 PSD
- **要最高质量**：极致档 + 手动选场景（自动检测偶尔会判断错）
- **要快**：经济档 + 关掉"检测文字"

---

## 💡 场景化最佳实践

### 电商主图（白底，单一产品）
- 档位：标准档
- 场景：电商商品图
- 期望：主体精抠 + 价格标/促销贴/二维码分别成层

### 电商详情页（长图，多元素+多段文字）
- 档位：极致档
- 场景：电商详情页/海报
- 期望：CTA 按钮、装饰图案、品牌色块各成层；文字按"标题/副标题/正文/价格"分组

### 人像/服饰
- 档位：标准档或极致档
- 场景：人物/生活方式
- 期望：人物精细抠图（启用 Portrait 专用模型），服饰/配件单独成层

### 生活方式图（食物、家居）
- 档位：标准档
- 场景：生活场景图
- 期望：食物/餐具/家具各成层

### 设计稿（无明显主体）
- 档位：极致档
- 场景：全场景
- 期望：尽可能多层（接受更多误检）

---

## ❓ 常见问题

### Q: 分层数感觉不够？
- 把 `最小元素面积` 调低（默认 2000 → 试 500）
- 升级到极致档
- 场景选「全场景」（最大召回但有误检）

### Q: 极致档识别出来的图层重叠太多？
正常。`_dedupe_masks` 会按 IoU 0.6 去重，但若小元素几乎在大元素内（如 T 恤上的 logo），会保留为独立层方便编辑。如果嫌乱，去掉勾选某个场景增强即可。

### Q: 中文 OCR 准确率高了吗？
PaddleOCR 3.x 中文准确率从 EasyOCR 的 70-80% 提升到 90%+，价格符号 ¥/$ 也识别得很准。

### Q: PS 2023 打开报错？
首次升级到新版后请**彻底重启 ComfyUI**（任务管理器确认无遗留 python.exe），节点 widget 可能要重新选一次档位（旧字符串已废弃）。

### Q: BiRefNet 慢？
默认用 FP32，1024×1024 输入。如要加速可改 `tikpan_segmentation_models.py` 里的 `birefnet_matting` 加 `.half()`（GPU 显存够时差不多快 2 倍）。

### Q: 二维码识别不出来？
确认 `pyzbar` 安装成功。Windows 系统还需要 `libzbar-64.dll`（pyzbar 安装包自带，一般无需手动处理）。如果还有问题就用 cv2 自带的 QRCodeDetector 兜底（只支持二维码，不支持条形码）。

### Q: 自动场景检测判断错了？
手动选场景即可。或在节点日志里看 `[Tikpan PSD] 自动检测场景: xxx`，知道它怎么判断的。

---

## 🔧 技术架构

### 文件分工

| 文件 | 职责 |
|------|------|
| `nodes/tikpan_smart_psd_layering.py` | ComfyUI 节点接口、依赖检查/安装、UI 参数 |
| `nodes/tikpan_psd_processor.py` | 业务管线（三档入口、场景路由、Mask → 图层）、PSD 输出 |
| `nodes/tikpan_segmentation_models.py` | 模型单例加载器（线程安全 lazy singleton）、场景 prompts、纯算法工具（k-means/字号聚类） |

### 降级链

```
BiRefNet (900MB) ─失败→ rembg+isnet (~170MB) ─失败→ 跳过
PaddleOCR (~200MB) ─失败→ EasyOCR (~64MB) ─失败→ 跳过
GroundingDINO (700MB, 极致档) ─失败→ 降级到 SAM2 自动密集多尺度
SAM2 (~180MB) ─失败→ 不分割元素，仅出主体/背景/文字
pyzbar ─失败→ cv2.QRCodeDetector ─失败→ 跳过二维码层
LaMa (极致档) ─失败→ 元素层不补全，背景保留空洞
```

任何降级都会在日志里明确写出来，便于诊断。

### 智能后处理

`_dedupe_masks(masks, iou_threshold=0.6)`：
- 按面积大→小排序
- IoU > 0.6 且包含度 < 85% 时去重（避免重复相似 mask）
- IoU > 85% 无脑去重（几乎完全重叠的）
- 包含度 ≥ 85% 时保留小元素（"大物体里的小细节"，如 T 恤上的 logo）

### 智能命名

`_name_element` 优先用 GroundingDINO 的语义 label：
- 有 label：`logo_左上_1` / `badge_中心_3` / `qrcode_1_https://t.cn`
- 无 label：`主产品_中心` / `大元素_左上_1` / `小装饰_顶部_3`（按面积+位置启发式）
- 色块层：`色块_#FF3344_1`（带 hex 颜色）

---

## 🧪 离线测试

```bash
cd ComfyUI/custom_nodes/ComfyUI-Tikpan-Pro
python tests/test_smart_layering_offline.py
```

涵盖 14 项契约测试（节点初始化、输入定义、场景路由、字号聚类、k-means 色块、二维码降级等），不下载模型也能跑。

---

## 📝 改动历史（PSD 节点）

- **2026-06** 商业级管线升级：BiRefNet + GroundingDINO + PaddleOCR + 场景预设系统（6 选项）+ 二维码/字号分组/品牌色块/人像专用模型
- **2026-06** PSD 输出升级到 psd-tools 兼容流程（PS 2023 兼容）
- **2026-05** 加入三档 SAM2/Inpainting 体系
