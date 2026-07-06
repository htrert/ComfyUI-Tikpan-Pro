import { ArrowRight, Sparkles } from "lucide-react";
import type { Template } from "../../types";
import { cn, formatTokens } from "../../lib";

const accentClasses: Record<Template["accent"], string> = {
  teal: "from-teal-100 via-white to-sky-100 text-teal-700",
  violet: "from-violet-100 via-white to-teal-100 text-violet-700",
  amber: "from-amber-100 via-white to-teal-100 text-amber-700",
  sky: "from-sky-100 via-white to-amber-100 text-sky-700",
};

export function TemplateCard({ template, onUse }: { template: Template; onUse: () => void }) {
  return (
    <article className="group overflow-hidden rounded-2xl border border-slate-200/70 bg-white/82 shadow-sm transition hover:-translate-y-0.5 hover:border-teal-200 hover:shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
      <div className={cn("h-28 bg-gradient-to-br p-4", accentClasses[template.accent])}>
        <div className="flex items-center justify-between">
          <span className="rounded-full bg-white/75 px-3 py-1 text-xs font-black shadow-sm">{template.category}</span>
          <Sparkles className="h-5 w-5" />
        </div>
      </div>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-black tracking-normal text-slate-950">{template.title}</h2>
            <p className="mt-2 text-sm font-semibold leading-6 text-slate-500">{template.description}</p>
          </div>
          <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{formatTokens(template.tokens)}</span>
        </div>
        <button
          className="mt-5 inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition group-hover:bg-teal-600"
          type="button"
          onClick={onUse}
        >
          带入工作台
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </article>
  );
}
