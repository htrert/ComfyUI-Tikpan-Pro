import { ArrowDown, ArrowUp, Check, Eye, Image, Menu, Palette, Plus, Save, Sparkles, ToggleRight } from "lucide-react";
import { useMemo, useState } from "react";
import { adminPlatformModel } from "../../../adminData";
import { creativeModels, modelCategories } from "../../../appData";
import { cn, formatTokens } from "../../../lib";
import type { ModelCategory } from "../../../types";
import { GlassCard } from "../../GlassCard";

const themePresets = [
  {
    key: "clean-ops",
    name: "清爽运营台",
    surface: "#f8faf7",
    primary: "#0f172a",
    accent: "#0f766e",
    tone: "高频工作、模型货架、后台管理",
  },
  {
    key: "studio-light",
    name: "创作工作室",
    surface: "#f7fbff",
    primary: "#1d4ed8",
    accent: "#d97706",
    tone: "模板广场、作品预览、轻量品牌感",
  },
  {
    key: "commercial",
    name: "商业转化",
    surface: "#fffaf1",
    primary: "#111827",
    accent: "#ea580c",
    tone: "电商素材、广告海报、活动投放",
  },
];

const publishSteps = [
  { label: "菜单分类", value: "model_categories" },
  { label: "模型卡片", value: "platform_models" },
  { label: "参数表单", value: "parameter_schema" },
  { label: "前台样式", value: "theme_settings" },
];

export function AdminFrontendConfig() {
  const [categories, setCategories] = useState(() => modelCategories.map((category) => ({ ...category })));
  const [selectedTheme, setSelectedTheme] = useState(themePresets[0].key);
  const [saved, setSaved] = useState(false);

  const visibleCategories = useMemo(
    () => categories.filter((category) => category.visible).sort((a, b) => a.sortOrder - b.sortOrder),
    [categories],
  );
  const previewModels = creativeModels.filter((model) => {
    const categoryKeys = model.categoryKeys?.length ? model.categoryKeys : [model.category];
    return categoryKeys.some((key) => visibleCategories.some((category) => category.key === key));
  });
  const theme = themePresets.find((item) => item.key === selectedTheme) ?? themePresets[0];

  const toggleCategory = (key: string) => {
    setCategories((current) => current.map((category) => (category.key === key ? { ...category, visible: !category.visible } : category)));
  };

  const moveCategory = (key: string, direction: -1 | 1) => {
    setCategories((current) => {
      const sorted = [...current].sort((a, b) => a.sortOrder - b.sortOrder);
      const index = sorted.findIndex((category) => category.key === key);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= sorted.length) return current;

      const currentOrder = sorted[index].sortOrder;
      sorted[index].sortOrder = sorted[nextIndex].sortOrder;
      sorted[nextIndex].sortOrder = currentOrder;
      return sorted;
    });
  };

  const saveDraft = () => {
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  };

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr] xl:items-end">
          <div>
            <p className="text-sm font-black text-teal-700">前台配置</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">菜单、模型和样式统一发布</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              你现在在账户中心的后台区域配置前台页面：菜单来自模型分类，模型卡片来自平台模型，输入控件来自参数 schema，主题样式由前台样式配置控制。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {publishSteps.map((step, index) => (
              <div key={step.value} className="rounded-xl border border-slate-200/70 bg-white/80 p-3">
                <p className="text-[11px] font-black text-slate-400">Step {index + 1}</p>
                <p className="mt-1 text-sm font-black text-slate-950">{step.label}</p>
                <p className="mt-1 truncate font-mono text-[11px] font-bold text-slate-400">{step.value}</p>
              </div>
            ))}
          </div>
        </div>
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="grid gap-4">
          <GlassCard className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-50 text-teal-700">
                    <Menu className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-lg font-black text-slate-950">前台菜单</p>
                    <p className="text-sm font-semibold text-slate-500">对应数据库 `model_categories`，控制工作台左侧分类。</p>
                  </div>
                </div>
              </div>
              <button className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white" type="button">
                <Plus className="h-4 w-4" />
                新增菜单
              </button>
            </div>

            <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
              <div className="hidden grid-cols-[64px_1fr_90px_120px_100px] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
                <span>排序</span>
                <span>菜单名称</span>
                <span>可见</span>
                <span>搜索别名</span>
                <span>操作</span>
              </div>
              {categories
                .slice()
                .sort((a, b) => a.sortOrder - b.sortOrder)
                .map((category, index) => (
                  <MenuRow
                    key={category.key}
                    category={category}
                    first={index === 0}
                    last={index === categories.length - 1}
                    onMove={moveCategory}
                    onToggle={toggleCategory}
                  />
                ))}
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-center gap-2">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-50 text-amber-700">
                  <Image className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-lg font-black text-slate-950">模型货架</p>
                  <p className="text-sm font-semibold text-slate-500">展示名称、简介、消耗和标签会直接影响前台模型卡片。</p>
                </div>
              </div>
              <span className="rounded-full bg-white px-3 py-2 text-xs font-black text-slate-500 shadow-sm">{previewModels.length} 个前台可见模型</span>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {creativeModels.map((model) => (
                <div key={model.id} className="rounded-2xl border border-slate-200/70 bg-white/82 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-black text-slate-950">{model.name}</p>
                      <p className="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">{model.description}</p>
                    </div>
                    <span className={cn("rounded-full px-2.5 py-1 text-[11px] font-black", model.health >= 95 ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")}>
                      {model.health}%
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {model.bestFor.slice(0, 3).map((item) => (
                      <span key={item} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-500">
                        {item}
                      </span>
                    ))}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs font-bold text-slate-500">
                    <span className="truncate font-mono">{model.platformModelId}</span>
                    <span>{formatTokens(model.cost)} / 次</span>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>

        <div className="grid content-start gap-4">
          <GlassCard className="p-5">
            <div className="flex items-center gap-2">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-sky-50 text-sky-700">
                <Palette className="h-4 w-4" />
              </span>
              <div>
                <p className="text-lg font-black text-slate-950">前台样式</p>
                <p className="text-sm font-semibold text-slate-500">控制页面气质，不改变模型调用链路。</p>
              </div>
            </div>
            <div className="mt-4 grid gap-2">
              {themePresets.map((preset) => (
                <button
                  key={preset.key}
                  className={cn(
                    "flex min-h-20 items-center gap-3 rounded-2xl border p-3 text-left transition",
                    selectedTheme === preset.key ? "border-slate-950 bg-white shadow-sm" : "border-slate-200/70 bg-white/70 hover:border-teal-200",
                  )}
                  type="button"
                  onClick={() => setSelectedTheme(preset.key)}
                >
                  <span className="grid shrink-0 grid-cols-3 overflow-hidden rounded-full border border-white shadow-sm">
                    {[preset.surface, preset.primary, preset.accent].map((color) => (
                      <span key={color} className="h-8 w-7" style={{ background: color }} />
                    ))}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-black text-slate-950">{preset.name}</span>
                    <span className="mt-1 block text-xs font-semibold leading-5 text-slate-500">{preset.tone}</span>
                  </span>
                  {selectedTheme === preset.key && <Check className="h-4 w-4 shrink-0 text-teal-700" />}
                </button>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700">
                  <Eye className="h-4 w-4" />
                </span>
                <p className="text-lg font-black text-slate-950">前台预览</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-black text-slate-500">{theme.name}</span>
            </div>

            <div className="mt-4 rounded-2xl border border-slate-200/70 bg-white p-3">
              <div className="flex flex-wrap gap-1.5">
                {visibleCategories.map((category) => (
                  <span key={category.key} className={cn("rounded-lg px-2.5 py-1.5 text-xs font-black", category.key === "all" ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-600")}>
                    {category.name}
                  </span>
                ))}
              </div>
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 text-white">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-black text-slate-950">{adminPlatformModel.displayName}</p>
                    <p className="mt-1 line-clamp-2 text-xs font-semibold leading-5 text-slate-500">{adminPlatformModel.description}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {adminPlatformModel.useCaseText.split("，").map((item) => (
                        <span key={item} className="rounded-full bg-white px-2 py-1 text-[11px] font-black text-slate-500 shadow-sm">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <p className="mt-3 text-xs font-semibold leading-5 text-slate-500">
                生产环境发布时，把这里的草稿保存到后台 API，再由 `/catalog` 返回给前台工作台。
              </p>
            </div>

            <button className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700" type="button" onClick={saveDraft}>
              <Save className="h-4 w-4" />
              {saved ? "已保存配置草稿" : "保存并预览配置"}
            </button>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

function MenuRow({
  category,
  first,
  last,
  onMove,
  onToggle,
}: {
  category: ModelCategory;
  first: boolean;
  last: boolean;
  onMove: (key: string, direction: -1 | 1) => void;
  onToggle: (key: string) => void;
}) {
  return (
    <div className="grid gap-3 border-t border-slate-100 px-4 py-3 md:grid-cols-[64px_1fr_90px_120px_100px] md:items-center">
      <div className="flex gap-1">
        <button
          aria-label="上移菜单"
          className="grid h-8 w-8 place-items-center rounded-lg bg-slate-100 text-slate-500 transition hover:bg-white hover:text-slate-950 disabled:opacity-35"
          disabled={first}
          type="button"
          onClick={() => onMove(category.key, -1)}
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
        <button
          aria-label="下移菜单"
          className="grid h-8 w-8 place-items-center rounded-lg bg-slate-100 text-slate-500 transition hover:bg-white hover:text-slate-950 disabled:opacity-35"
          disabled={last}
          type="button"
          onClick={() => onMove(category.key, 1)}
        >
          <ArrowDown className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-black text-slate-950">{category.name}</p>
        <p className="truncate font-mono text-xs font-bold text-slate-400">{category.key}</p>
      </div>
      <button
        className={cn(
          "inline-flex h-8 w-fit items-center gap-1.5 rounded-full px-3 text-xs font-black transition",
          category.visible ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500",
        )}
        type="button"
        onClick={() => onToggle(category.key)}
      >
        <ToggleRight className="h-3.5 w-3.5" />
        {category.visible ? "显示" : "隐藏"}
      </button>
      <p className="truncate text-xs font-semibold text-slate-500">{category.aliases?.join("、") || "-"}</p>
      <button className="h-8 rounded-lg bg-white px-3 text-xs font-black text-slate-600 shadow-sm transition hover:text-teal-700" type="button">
        编辑
      </button>
    </div>
  );
}
