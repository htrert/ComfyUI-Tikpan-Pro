import { Eye, Plus, Save, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { adminParameters, adminPlatformModel } from "../../../adminData";
import { GlassCard } from "../../GlassCard";

export function AdminModels() {
  const [modelName, setModelName] = useState(adminPlatformModel.displayName);
  const [category, setCategory] = useState(adminPlatformModel.category);
  const [description, setDescription] = useState(adminPlatformModel.description);
  const [useCases, setUseCases] = useState(adminPlatformModel.useCaseText);
  const [cost, setCost] = useState(adminPlatformModel.estimatedCost);
  const [saved, setSaved] = useState(false);

  const saveDraft = () => {
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  };

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">模型配置</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">前台模型与参数</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              这里配置用户看到的模型名称、分类、简介和表单参数。生产环境中，这些内容对应 `platform_models`、模型分类关联和参数 schema。
            </p>
          </div>
          <button className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-700" type="button">
            <Plus className="h-4 w-4" />
            新增模型
          </button>
        </div>
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <GlassCard className="p-5">
          <div className="grid gap-4 lg:grid-cols-3">
            <Field label="前台展示名称" value={modelName} onChange={setModelName} />
            <Field label="所属分类" value={category} onChange={setCategory} />
            <Field label="预计消耗" value={cost} onChange={setCost} />
          </div>
          <label className="mt-4 grid gap-2">
            <span className="text-xs font-black text-slate-500">前台模型简介</span>
            <textarea
              className="min-h-24 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-sm font-bold leading-6 text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <Field label="应用场景标签" value={useCases} onChange={setUseCases} />
            <button className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700" type="button" onClick={saveDraft}>
              <Save className="h-4 w-4" />
              {saved ? "已保存模型草稿" : "保存模型草稿"}
            </button>
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700">
              <Eye className="h-4 w-4" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">前台卡片预览</p>
              <p className="text-sm font-semibold text-slate-500">保存后同步到工作台模型列表。</p>
            </div>
          </div>
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-black text-teal-700">{category || "未选择分类"}</p>
            <p className="mt-2 text-lg font-black text-slate-950">{modelName || "未命名模型"}</p>
            <p className="mt-1 text-sm font-semibold leading-6 text-slate-600">{description || "暂无简介"}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {useCases
                .split(/[，,]/)
                .map((item) => item.trim())
                .filter(Boolean)
                .map((item) => (
                  <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">
                    {item}
                  </span>
                ))}
            </div>
            <p className="mt-4 text-xs font-black text-slate-500">{cost || "未设置消耗"}</p>
          </div>
        </GlassCard>
      </div>

      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <SlidersHorizontal className="h-4 w-4" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">参数 schema</p>
              <p className="text-sm font-semibold text-slate-500">前台输入控件会根据这里的参数类型自动渲染。</p>
            </div>
          </div>
          <button className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-white px-4 text-sm font-black text-slate-600 shadow-sm transition hover:text-teal-700" type="button">
            <Plus className="h-4 w-4" />
            新增参数
          </button>
        </div>
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
          <div className="hidden grid-cols-[1fr_1fr_0.8fr_1fr_0.7fr] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
            <span>参数 key</span>
            <span>前台标签</span>
            <span>控件类型</span>
            <span>默认值</span>
            <span>必填</span>
          </div>
          {adminParameters.map((parameter) => (
            <div key={parameter.key} className="grid gap-2 border-t border-slate-100 px-4 py-3 md:grid-cols-[1fr_1fr_0.8fr_1fr_0.7fr] md:items-center">
              <span className="font-mono text-sm font-black text-slate-900">{parameter.key}</span>
              <span className="text-sm font-bold text-slate-600">{parameter.label}</span>
              <span className="text-sm font-bold text-slate-500">{parameter.type}</span>
              <span className="text-sm font-bold text-slate-500">{parameter.defaultValue || "-"}</span>
              <span className="text-sm font-bold text-slate-500">{parameter.required ? "是" : "否"}</span>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-black text-slate-500">{label}</span>
      <input
        className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
