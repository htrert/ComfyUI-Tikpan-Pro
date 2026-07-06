import type { CreativeModel } from "../../types";
import { cn, formatTokens } from "../../lib";

export function ModelCard({ active, model, onSelect }: { active: boolean; model: CreativeModel; onSelect: () => void }) {
  const Icon = model.icon;

  return (
    <button
      className={cn(
        "min-w-0 w-full rounded-xl border p-3 text-left transition",
        active ? "active-sheen border-[#b899ff] bg-[#eee6ff] shadow-[0_14px_32px_rgba(121,86,220,0.14)] ring-2 ring-[#dac9ff]" : "border-transparent bg-white/58 hover:border-[#cdb8ff] hover:bg-white/80",
      )}
      type="button"
      onClick={onSelect}
    >
      <div className="flex min-w-0 items-start gap-3">
        <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-lg", active ? "bg-white text-[#e56f45] shadow-sm" : "bg-white text-slate-500 shadow-sm")}>
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-black text-slate-950">{model.name}</span>
          <span className="mt-1 block truncate text-xs font-semibold text-slate-500">{model.description}</span>
        </span>
        <span className="shrink-0 text-xs font-black text-emerald-600">{model.health}%</span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap gap-1">
          {model.tags.slice(0, 2).map((tag) => (
            <span key={tag} className={cn("rounded-full px-2 py-1 text-[11px] font-black shadow-sm", active ? "bg-white/80 text-[#6d32d9]" : "bg-white text-slate-500")}>
              {tag}
            </span>
          ))}
        </div>
        <span className="shrink-0 text-xs font-black text-slate-500">{formatTokens(model.cost)} / 次</span>
      </div>
    </button>
  );
}
