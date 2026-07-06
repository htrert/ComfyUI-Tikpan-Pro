import { BadgeCheck, Download, FileJson, ImagePlus, Maximize2, PackageOpen, Save, Sparkles, Video } from "lucide-react";
import type { CreativeModel } from "../../types";
import { cn } from "../../lib";

const roleChips = [
  { label: "官方", icon: Sparkles },
  { label: "商品主图", icon: PackageOpen },
  { label: "广告海报", icon: ImagePlus },
  { label: "4K 输出", icon: BadgeCheck },
  { label: "异步生成", icon: FileJson },
  { label: "视频模型可扩展", icon: Video },
];

export function ResultPanel({ generatedPrompt, model }: { generatedPrompt: string; model: CreativeModel }) {
  const Icon = model.icon;

  return (
    <div className="relative flex min-h-[430px] flex-1 flex-col">
      <div className="absolute right-0 top-0 hidden items-center gap-2 lg:flex">
        {["置顶", "玩法说明", "选择角色"].map((item, index) => (
          <button
            key={item}
            className={cn(
              "h-11 rounded-full border px-4 text-sm font-black shadow-sm transition",
              index === 1
                ? "border-[#9b72ff]/45 bg-[#efe7ff] text-[#6d32d9] shadow-[#8f5cff]/10"
                : "border-[#ded5f6] bg-white/55 text-slate-600 hover:border-[#bda8ff] hover:bg-white",
            )}
            type="button"
          >
            {item}
          </button>
        ))}
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-3 py-8 text-center md:py-10">
        <span className="claude-burst pulse-ring grid h-16 w-16 place-items-center rounded-full bg-white/70 text-[#e56f45] shadow-[0_24px_70px_rgba(121,86,220,0.16)] ring-1 ring-[#eadfff]">
          <Icon className="h-8 w-8" />
        </span>
        <h1 className="mt-6 text-3xl font-black tracking-normal text-slate-950 md:text-4xl">{model.name}</h1>
        <p className="mt-3 text-xs font-black uppercase tracking-[0.28em] text-slate-700">{model.group}</p>
        <div className="mt-7 max-w-2xl rounded-2xl border border-[#8b5cf6] bg-white/48 px-6 py-4 shadow-[0_18px_60px_rgba(139,92,246,0.09)] backdrop-blur-xl">
          <p className="text-sm font-black leading-8 text-slate-700">{model.description} 打开即可开始创作。</p>
        </div>

        {generatedPrompt && (
          <div className="mt-8 w-full max-w-3xl rounded-3xl border border-[#ded5ff] bg-white/82 p-4 text-left shadow-[0_18px_60px_rgba(121,86,220,0.12)] backdrop-blur-2xl">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-black text-[#6d32d9]">已生成草稿</p>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-700">{generatedPrompt}</p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <button className="inline-flex items-center gap-2 rounded-full bg-[#4b16d1] px-4 py-2 text-xs font-black text-white" type="button">
                  <Save className="h-3.5 w-3.5" />
                  保存
                </button>
                <button className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-black text-slate-600 shadow-sm" type="button">
                  <Download className="h-3.5 w-3.5" />
                  下载
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mx-auto flex w-full max-w-5xl gap-2 overflow-x-auto pb-2">
        {roleChips.map((chip, index) => {
          const ChipIcon = chip.icon;
          return (
            <button
              key={chip.label}
              className={cn(
                "inline-flex h-9 shrink-0 items-center gap-2 rounded-full border px-4 text-xs font-black shadow-sm transition",
                index === 0
                  ? "border-[#cdb8ff] bg-[#e9ddff] text-[#6d32d9]"
                  : "border-[#ded5f6] bg-white/68 text-slate-600 hover:border-[#bda8ff] hover:text-[#6d32d9]",
              )}
              type="button"
            >
              <ChipIcon className="h-3.5 w-3.5" />
              {chip.label}
            </button>
          );
        })}
      </div>

      <div className="sr-only">
        <div className="result-tile relative overflow-hidden rounded-2xl">
          {generatedPrompt ? (
            <div className="absolute inset-0 flex flex-col justify-end p-5">
              <div className="max-w-xl rounded-2xl bg-white/82 p-4 shadow-sm backdrop-blur">
                <p className="text-xs font-black text-[#6d32d9]">已生成草稿</p>
                <p className="mt-2 line-clamp-3 text-sm font-semibold leading-6 text-slate-700">{generatedPrompt}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="inline-flex items-center gap-2 rounded-full bg-[#4b16d1] px-4 py-2 text-xs font-black text-white" type="button">
                    <Save className="h-3.5 w-3.5" />
                    保存到作品库
                  </button>
                  <button className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-black text-slate-600 shadow-sm" type="button">
                    <Download className="h-3.5 w-3.5" />
                    下载
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div />
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
          {["画面方向", "可继续创作", "作品归档"].map((title, index) => (
            <div key={title} className={cn("rounded-2xl border border-white/75 bg-white/65 p-4 shadow-sm", index === 1 && "bg-[#f2ebff]/80")}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-black text-slate-950">{title}</p>
                <Maximize2 className="h-4 w-4 text-slate-400" />
              </div>
              <p className="mt-2 text-xs font-semibold leading-5 text-slate-500">
                {index === 0 && "先看整体方向，再决定是否扩展更多版本。"}
                {index === 1 && "生成后可放大、改写、换风格或追加版本。"}
                {index === 2 && "满意的结果可以保存，后续在作品库继续使用。"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
