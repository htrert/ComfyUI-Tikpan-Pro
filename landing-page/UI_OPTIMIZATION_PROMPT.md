# AI 聚合平台首页 UI 优化说明

请帮我优化一个 AI 聚合平台单页网站的 UI。这个页面已经用 React + TypeScript + Vite + Tailwind CSS + framer-motion + lucide-react 实现，不使用任何图片、视频或远程素材，所有视觉效果都由前端代码生成。

## 项目定位

这是一个面向中文用户的 AI 聚合平台首页，平台能力包括：

- 聚合图像、视频、音频、文本、智能体工作流等 AI 模型
- 提供统一模型目录、参数表单、任务队列和生成结果展示
- 支持渠道路由、余额计费、失败重试、历史记录和 API 能力
- 目标风格是明亮、高级、现代 SaaS、AI 工作台感

## 当前技术栈

- React
- TypeScript
- Vite
- Tailwind CSS
- framer-motion
- lucide-react

## 重要约束

请严格遵守：

- 不要使用图片素材
- 不要使用视频素材
- 不要使用远程素材 URL
- 不要依赖 stock photo、背景视频、外链插图
- 所有视觉都应通过 CSS、React 组件、渐变、边框、动效、图标、布局生成
- 保持移动端适配，不能横向溢出
- 保持中文文案可读
- 页面不要变成暗黑风格
- 页面应该有光效、动效、空间层次和科技感，但不能花哨到影响阅读

## 当前视觉方向

当前版本已经从黑暗风格改成浅色风格：

- 背景色：接近 `#f8faf7`
- 有浅色网格背景
- 有柔和青绿、蓝色、金色光效
- 有玻璃拟态卡片
- 有发光边框
- 有流动光束
- 有小闪点
- 有卡片悬浮动画
- 有进度条动画
- 有滚动日志 ticker

希望你继续优化它，让它更像一个成熟商业化 AI 平台，而不是模板页。

## 当前页面结构

页面是单页 landing page，包含 5 个区块：

1. Hero 首屏
   - 顶部导航：Tikpan AI Hub、Models、Workflow、Services、Login
   - 主标题：聚合主流 AI 模型平台，把生成能力变成产品。
   - 副标题：解释用一个网站管理图像、视频、音频、文本和工作流模型
   - CTA：查看控制台、生成一次任务
   - 统计卡片：86+ 模型接入、99.4% 任务成功率、12ms 路由决策
   - 右侧是前端生成的 Generation Console 控制台

2. Platform Core
   - 展示平台核心指标
   - 卡片包括统一模型目录、平均路由耗时、失败自动退款、任务状态追踪

3. Generated UI Preview / Workflow
   - 展示任务链路
   - 包含 Input、Route、Cost 状态卡片
   - 中间有步骤节点和连接线
   - 下方有任务日志表格

4. Philosophy / Commercial Loop
   - 展示从模型调用到商业闭环
   - 左侧是请求生命周期
   - 右侧是 Model Hub、Pipeline、Billing、API 能力卡片

5. Services
   - 展示可售卖能力
   - 图像生成、视频生成、音频生成、智能体工作流
   - 底部有滚动事件日志条

## 希望你重点优化的方向

请重点优化这些方面：

- 首屏视觉更有冲击力，但保持清爽
- 右侧控制台更像真实产品界面，不要太空
- 光效更自然，有层次但不要廉价
- 卡片层级更清楚，视觉重心更明确
- 中文标题排版更高级
- 移动端首屏更紧凑，内容不要显得太长
- 各区块之间的节奏更自然
- CTA 更突出
- 不要把页面做成营销大字报，应该更像一个可信的 AI SaaS 产品

## 当前核心 CSS 效果

当前已有这些 CSS 工具类：

- `.liquid-glass`：浅色玻璃拟态卡片
- `.light-shell`：浅色网格背景
- `.light-beam`：横向流动光束
- `.soft-sheen`：卡片扫光
- `.glow-border`：旋转发光边框
- `.progress-bar`：动态进度条
- `.data-ticker`：滚动日志
- `.float-soft`：轻微上下浮动
- `.dash-line`：虚线连接线
- `.spark`：小光点漂移动效

## 代码文件结构

主要文件：

```text
landing-page/src/App.tsx
landing-page/src/index.css
landing-page/src/constants.ts
landing-page/src/components/Hero.tsx
landing-page/src/components/AboutSection.tsx
landing-page/src/components/FeaturedVideoSection.tsx
landing-page/src/components/PhilosophySection.tsx
landing-page/src/components/ServicesSection.tsx
```

## 当前运行方式

```bash
cd landing-page
npm install
npm run dev
```

本地预览：

```text
http://localhost:5173/
```

## 交付要求

请输出以下内容之一：

1. 直接给出优化后的 React + Tailwind 代码修改建议
2. 或给出详细 UI 优化方案，包括布局、颜色、动效、组件层次和移动端调整
3. 如果可以，请优先给出可直接替换的组件代码和 CSS

请不要建议使用图片、视频或外部素材。这个页面必须保持纯前端生成视觉。
