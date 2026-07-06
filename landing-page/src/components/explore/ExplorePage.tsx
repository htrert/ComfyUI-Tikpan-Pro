import { ArrowRight, Flame, LayoutGrid, Megaphone, Newspaper, Search, Store } from "lucide-react";
import { featuredTemplates, workflowHighlights } from "../../appData";
import type { Template } from "../../types";
import { GlassCard } from "../GlassCard";
import { TemplateCard } from "./TemplateCard";

export function ExplorePage({ onUseTemplate }: { onUseTemplate: (template: Template) => void }) {
  return (
    <div className="min-h-[calc(100vh-64px)] bg-[#f8faf7]">
      <div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:py-8">
        <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <GlassCard className="p-6 lg:p-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-black text-teal-700 shadow-sm">
              <Flame className="h-3.5 w-3.5" />
              探索广场
            </div>
            <h1 className="mt-5 max-w-3xl text-3xl font-black tracking-normal text-slate-950 md:text-5xl">先看灵感，再一键带入工作台。</h1>
            <p className="mt-4 max-w-2xl text-base font-semibold leading-8 text-slate-600">
              从行业模板、热门能力和模型示例里挑一个方向，直接开始今天的素材创作。
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {["内容广场", "应用市场", "行业模板", "系统公告"].map((item) => (
                <button key={item} className="rounded-full bg-white/80 px-4 py-2 text-sm font-black text-slate-600 shadow-sm transition hover:bg-slate-950 hover:text-white" type="button">
                  {item}
                </button>
              ))}
            </div>
          </GlassCard>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            {workflowHighlights.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="rounded-2xl border border-slate-200/70 bg-white/78 p-5 shadow-sm">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
                      <Icon className="h-4 w-4" />
                    </span>
                    <p className="font-black text-slate-950">{item.title}</p>
                  </div>
                  <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">{item.copy}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mt-6 grid gap-4 xl:grid-cols-[0.72fr_1.28fr]">
          <GlassCard className="p-5">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-violet-50 text-violet-700">
                <Search className="h-5 w-5" />
              </span>
              <div>
                <p className="text-lg font-black text-slate-950">热门能力</p>
                <p className="mt-1 text-sm font-semibold text-slate-500">更适合高频商业素材的创作方向。</p>
              </div>
            </div>
            <div className="mt-5 grid gap-3">
              {[
                { icon: LayoutGrid, title: "电商主图", copy: "新品、白底图、场景图、卖点图。" },
                { icon: Megaphone, title: "广告海报", copy: "活动预热、投放素材、品牌视觉。" },
                { icon: Store, title: "直播间脚本", copy: "开场、转场、卖点、催单话术。" },
                { icon: Newspaper, title: "内容选题", copy: "标题、封面、正文和话题组合。" },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="flex items-start gap-3 rounded-xl border border-slate-200/70 bg-white/72 p-3">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
                    <div>
                      <p className="text-sm font-black text-slate-950">{item.title}</p>
                      <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{item.copy}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </GlassCard>

          <div>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-xl font-black text-slate-950">今日精选模板</p>
                <p className="mt-1 text-sm font-semibold text-slate-500">选择一个模板，带入工作台继续创作。</p>
              </div>
              <ArrowRight className="hidden h-5 w-5 text-slate-400 sm:block" />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {featuredTemplates.map((template) => (
                <TemplateCard key={template.id} template={template} onUse={() => onUseTemplate(template)} />
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
