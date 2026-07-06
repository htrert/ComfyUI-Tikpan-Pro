import { History, Plus, Search, Settings2 } from "lucide-react";
import type { CapabilityCategory, CreativeModel } from "../../types";
import { currentUser } from "../../appData";
import { cn, formatTokens } from "../../lib";
import { ModelCard } from "./ModelCard";

type WorkspaceSidebarProps = {
  category: CapabilityCategory;
  query: string;
  selectedModelId: string;
  tabs: Array<{ key: CapabilityCategory; label: string }>;
  models: CreativeModel[];
  onCategoryChange: (category: CapabilityCategory) => void;
  onModelSelect: (model: CreativeModel) => void;
  onQueryChange: (value: string) => void;
};

export function WorkspaceSidebar({
  category,
  query,
  selectedModelId,
  tabs,
  models,
  onCategoryChange,
  onModelSelect,
  onQueryChange,
}: WorkspaceSidebarProps) {
  const grouped = models.reduce<Record<string, CreativeModel[]>>((acc, model) => {
    acc[model.group] = acc[model.group] ?? [];
    acc[model.group].push(model);
    return acc;
  }, {});

  return (
    <div className="sticky top-16 flex h-[calc(100vh-64px)] flex-col gap-4 overflow-hidden p-4">
      <button className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#4b16d1] px-4 text-sm font-black text-white shadow-[0_14px_34px_rgba(75,22,209,0.25)] transition hover:bg-[#3b12a8]" type="button">
        <Plus className="h-4 w-4" />
        新建创作
      </button>

      <div className="flex flex-wrap gap-1.5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={cn(
              "h-8 rounded-lg px-2.5 text-xs font-black transition",
              category === tab.key ? "bg-[#e6dcff] text-[#6d32d9] ring-1 ring-[#dac9ff]" : "text-slate-600 hover:bg-white/80 hover:text-[#6d32d9]",
            )}
            type="button"
            onClick={() => onCategoryChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          className="h-11 w-full rounded-2xl border border-[#ded5f6] bg-white/58 pl-9 pr-3 text-sm font-semibold text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#b899ff] focus:ring-4 focus:ring-[#e6dcff]"
          placeholder="搜索模型、能力或别名..."
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
        />
      </label>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {Object.entries(grouped).map(([group, groupModels]) => (
          <div key={group} className="mb-4">
            <p className="mb-2 px-1 text-xs font-black text-slate-400">{group}</p>
            <div className="grid min-w-0 gap-2">
              {groupModels.map((model) => (
                <ModelCard key={model.id} active={model.id === selectedModelId} model={model} onSelect={() => onModelSelect(model)} />
              ))}
            </div>
          </div>
        ))}
        {models.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[#cdb8ff] bg-white/65 p-4 text-center text-sm font-bold leading-6 text-slate-500">
            这个分类还没有可见模型。你可以在后台新增分类、绑定模型、调整排序后发布到前台。
          </div>
        )}
      </div>

      <div className="grid gap-2">
        <div className="rounded-xl border border-[#dac9ff] bg-[#eee6ff]/70 p-3">
          <div className="flex items-start gap-2">
            <Settings2 className="mt-0.5 h-4 w-4 shrink-0 text-[#6d32d9]" />
            <p className="text-xs font-bold leading-5 text-[#5f3aae]">左侧菜单、模型名称、标签和参数由后台「前台配置 / 模型配置」维护。</p>
          </div>
        </div>
        <button className="flex items-center gap-2 rounded-xl border border-[#ded5f6] bg-white/65 px-3 py-3 text-sm font-bold text-slate-600 shadow-sm transition hover:border-[#b899ff] hover:text-[#6d32d9]" type="button">
          <History className="h-4 w-4" />
          历史记录
        </button>
        <div className="flex items-center justify-between gap-3 rounded-xl bg-white/80 p-3 shadow-sm">
          <div className="flex min-w-0 items-center gap-2">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#4b16d1] via-[#7c3aed] to-[#b899ff] text-xs font-black text-white">
              {currentUser.initials}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-black text-slate-950">{currentUser.name}</p>
              <p className="truncate text-xs font-bold text-amber-600">{formatTokens(currentUser.tokens)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
