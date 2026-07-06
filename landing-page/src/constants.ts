import type { LucideIcon } from "lucide-react";
import {
  AudioLines,
  Clapperboard,
  FileText,
  Image,
  Layers3,
  ShieldCheck,
  Sparkles,
  WandSparkles,
  Workflow,
  Zap,
} from "lucide-react";

export type ModelCard = {
  name: string;
  type: string;
  latency: string;
  status: "Ready" | "Queued" | "Routing";
  accent: string;
};

export const modelCards: ModelCard[] = [
  {
    name: "Image Studio",
    type: "Text to image",
    latency: "2.4s",
    status: "Ready",
    accent: "from-teal-300 via-cyan-300 to-sky-300",
  },
  {
    name: "Video Forge",
    type: "Image to video",
    latency: "8.9s",
    status: "Routing",
    accent: "from-indigo-300 via-blue-300 to-cyan-200",
  },
  {
    name: "Voice Lab",
    type: "Music & speech",
    latency: "1.8s",
    status: "Ready",
    accent: "from-amber-200 via-orange-200 to-rose-200",
  },
  {
    name: "Text Agent",
    type: "Copy & workflow",
    latency: "0.7s",
    status: "Queued",
    accent: "from-lime-200 via-emerald-200 to-teal-200",
  },
];

export const capabilities: Array<{
  icon: LucideIcon;
  label: string;
  title: string;
  description: string;
}> = [
  {
    icon: Layers3,
    label: "All-in-one",
    title: "一个入口完成多种创作",
    description:
      "不用来回切换不同工具，图片、视频、音频、文案和自动化任务都可以在同一个工作台完成。",
  },
  {
    icon: Workflow,
    label: "Workflow",
    title: "从想法到成品更顺手",
    description:
      "选择创作类型、填写需求、上传素材、等待生成、下载结果，每一步都清楚直观。",
  },
  {
    icon: ShieldCheck,
    label: "Reliable",
    title: "生成过程更稳定可控",
    description:
      "任务进度、消耗预估、结果记录都能看见，生成失败也有清晰提示和处理方式。",
  },
  {
    icon: Sparkles,
    label: "Output",
    title: "结果可以沉淀复用",
    description:
      "生成过的图片、视频、音频和文案都可以统一管理，方便对比、复用和继续迭代。",
  },
];

export const workflowSteps = [
  { icon: FileText, title: "描述需求", detail: "用中文写清楚想要的画面、视频、声音或文案" },
  { icon: Image, title: "选择能力", detail: "按目标选择图片、视频、音频、文案或智能体工具" },
  { icon: Zap, title: "一键生成", detail: "系统自动处理任务，并实时展示进度和消耗预估" },
  { icon: Sparkles, title: "下载成品", detail: "保存结果、继续优化，或在历史记录里随时找回" },
];

export const servicePanels = [
  {
    icon: Image,
    label: "Image",
    title: "图像生成",
    copy: "快速生成海报、商品图、头像、封面和社媒配图，也可以基于参考图继续优化。",
  },
  {
    icon: Clapperboard,
    label: "Video",
    title: "视频生成",
    copy: "把图片、脚本或创意变成短视频素材，适合广告、内容种草和视觉概念验证。",
  },
  {
    icon: AudioLines,
    label: "Audio",
    title: "音频生成",
    copy: "生成配音、音乐、歌词和内容旁白，让视频、课程和营销素材更完整。",
  },
  {
    icon: WandSparkles,
    label: "Agent",
    title: "文案与智能助手",
    copy: "帮你写营销文案、整理脚本、扩写创意，也能把重复工作交给智能助手处理。",
  },
];
