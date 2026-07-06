import { Eye, Loader2, Plus, Save, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  listRemotePlatformModels,
  upsertRemotePlatformModel,
  type PlatformModelUpsert,
} from "../../../apiClient";
import {
  platformModels as localPlatformModels,
  type Modality,
  type PlatformModel,
  type SchemaField,
} from "../../../productData";
import { cn } from "../../../lib";
import { GlassCard } from "../../GlassCard";

const modalities: Modality[] = ["image", "video", "chat", "audio", "workflow"];
const tiers: PlatformModel["tier"][] = ["Lite", "Standard", "Pro", "Ultra"];

type ModelDraft = {
  id: string;
  name: string;
  shortName: string;
  modality: Modality;
  tier: PlatformModel["tier"];
  description: string;
  useCasesText: string;
  price: string;
  eta: string;
  visible: boolean;
  recommended: boolean;
  schema: SchemaField[];
};

export function AdminModels() {
  const [models, setModels] = useState<PlatformModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [draft, setDraft] = useState<ModelDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadModels() {
      try {
        setLoading(true);
        const remoteModels = await listRemotePlatformModels(localPlatformModels);
        if (cancelled) return;
        setModels(remoteModels);
        const first = remoteModels[0];
        setSelectedModelId((current) => current || first?.id || "");
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setModels(localPlatformModels);
        setSelectedModelId((current) => current || localPlatformModels[0]?.id || "");
        setMessage(error instanceof Error ? error.message : "Model admin API is unavailable. Showing local catalog.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) ?? models[0] ?? null,
    [models, selectedModelId],
  );

  useEffect(() => {
    if (!selectedModel) {
      setDraft(null);
      return;
    }
    setDraft(modelToDraft(selectedModel));
  }, [selectedModel]);

  async function saveModel() {
    if (!draft) return;

    const input: PlatformModelUpsert = {
      id: draft.id,
      slug: selectedModel?.slug ?? draft.id,
      display_name: draft.name,
      name: draft.name,
      short_name: draft.shortName || draft.name,
      modality: draft.modality,
      tier: draft.tier,
      description: draft.description,
      use_cases: splitList(draft.useCasesText),
      visible: draft.visible,
      recommended: draft.recommended,
      estimated_cost: draft.price,
      estimated_time: draft.eta,
      sort_order: models.findIndex((model) => model.id === draft.id),
      schema: draft.schema,
    };

    try {
      setSaving(true);
      const saved = await upsertRemotePlatformModel(input, draft.id);
      const nextModel = mergeSavedModel(selectedModel, saved, draft);
      setModels((current) => current.map((model) => (model.id === nextModel.id ? nextModel : model)));
      setMessage(`Saved ${nextModel.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Model save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Model configuration</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Frontend models and parameters</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              Edit the live platform model record that powers the workspace catalog and routing schema.
            </p>
          </div>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!draft || saving}
            type="button"
            onClick={() => void saveModel()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save model
          </button>
        </div>
        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <GlassCard className="p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-sm font-black text-slate-950">Catalog</p>
            {loading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
          </div>
          <div className="grid gap-2">
            {models.map((model) => (
              <button
                key={model.id}
                className={cn(
                  "rounded-2xl border p-3 text-left transition",
                  selectedModelId === model.id ? "border-teal-300 bg-teal-50/80" : "border-slate-200 bg-white/80 hover:border-slate-300",
                )}
                type="button"
                onClick={() => setSelectedModelId(model.id)}
              >
                <p className="truncate text-sm font-black text-slate-950">{model.name}</p>
                <p className="mt-1 truncate text-xs font-bold text-slate-500">{model.id}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-black text-slate-500">{model.modality}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-black text-slate-500">{model.tier}</span>
                </div>
              </button>
            ))}
          </div>
        </GlassCard>

        <div className="grid min-w-0 gap-4">
          {draft && (
            <GlassCard className="p-5">
              <div className="grid gap-4 lg:grid-cols-3">
                <Field label="Display name" value={draft.name} onChange={(value) => setDraft({ ...draft, name: value })} />
                <Field label="Short name" value={draft.shortName} onChange={(value) => setDraft({ ...draft, shortName: value })} />
                <Field label="Estimated cost" value={draft.price} onChange={(value) => setDraft({ ...draft, price: value })} />
                <SelectField
                  label="Modality"
                  options={modalities}
                  value={draft.modality}
                  onChange={(value) => setDraft({ ...draft, modality: value as Modality })}
                />
                <SelectField
                  label="Tier"
                  options={tiers}
                  value={draft.tier}
                  onChange={(value) => setDraft({ ...draft, tier: value as PlatformModel["tier"] })}
                />
                <Field label="Estimated time" value={draft.eta} onChange={(value) => setDraft({ ...draft, eta: value })} />
              </div>
              <label className="mt-4 grid gap-2">
                <span className="text-xs font-black text-slate-500">Description</span>
                <textarea
                  className="min-h-24 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-sm font-bold leading-6 text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
                  value={draft.description}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                />
              </label>
              <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_auto_auto] lg:items-end">
                <Field label="Use cases, comma separated" value={draft.useCasesText} onChange={(value) => setDraft({ ...draft, useCasesText: value })} />
                <Toggle label="Visible" value={draft.visible} onChange={(value) => setDraft({ ...draft, visible: value })} />
                <Toggle label="Recommended" value={draft.recommended} onChange={(value) => setDraft({ ...draft, recommended: value })} />
              </div>
            </GlassCard>
          )}

          {draft && <ModelPreview draft={draft} />}
          {draft && <SchemaTable schema={draft.schema} />}
        </div>
      </div>
    </div>
  );
}

function ModelPreview({ draft }: { draft: ModelDraft }) {
  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700">
          <Eye className="h-4 w-4" />
        </span>
        <div>
          <p className="text-lg font-black text-slate-950">Workspace card preview</p>
          <p className="text-sm font-semibold text-slate-500">Saved fields sync back to the admin catalog API.</p>
        </div>
      </div>
      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-black text-teal-700">{draft.modality}</p>
        <p className="mt-2 text-lg font-black text-slate-950">{draft.name || "Untitled model"}</p>
        <p className="mt-1 text-sm font-semibold leading-6 text-slate-600">{draft.description || "No description yet."}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {splitList(draft.useCasesText).map((item) => (
            <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">
              {item}
            </span>
          ))}
        </div>
        <p className="mt-4 text-xs font-black text-slate-500">
          {draft.price || "No price"} · {draft.eta || "No ETA"}
        </p>
      </div>
    </GlassCard>
  );
}

function SchemaTable({ schema }: { schema: SchemaField[] }) {
  return (
    <GlassCard className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-50 text-teal-700">
            <SlidersHorizontal className="h-4 w-4" />
          </span>
          <div>
            <p className="text-lg font-black text-slate-950">Parameter schema</p>
            <p className="text-sm font-semibold text-slate-500">The workspace parameter panel renders from these fields.</p>
          </div>
        </div>
        <button className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-white px-4 text-sm font-black text-slate-600 shadow-sm transition hover:text-teal-700" type="button">
          <Plus className="h-4 w-4" />
          Add parameter
        </button>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
        <div className="hidden grid-cols-[1fr_1fr_0.8fr_1fr_0.7fr] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
          <span>Key</span>
          <span>Label</span>
          <span>Type</span>
          <span>Default</span>
          <span>Required</span>
        </div>
        {schema.map((parameter) => (
          <div key={parameter.key} className="grid gap-2 border-t border-slate-100 px-4 py-3 md:grid-cols-[1fr_1fr_0.8fr_1fr_0.7fr] md:items-center">
            <span className="font-mono text-sm font-black text-slate-900">{parameter.key}</span>
            <span className="text-sm font-bold text-slate-600">{parameter.label}</span>
            <span className="text-sm font-bold text-slate-500">{parameter.type}</span>
            <span className="text-sm font-bold text-slate-500">{String(parameter.defaultValue ?? parameter.value ?? "-")}</span>
            <span className="text-sm font-bold text-slate-500">{parameter.required ? "Yes" : "No"}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function modelToDraft(model: PlatformModel): ModelDraft {
  return {
    id: model.id,
    name: model.name,
    shortName: model.shortName,
    modality: model.modality,
    tier: normalizeTier(model.tier),
    description: model.description,
    useCasesText: model.useCases.join(", "),
    price: model.price,
    eta: model.eta,
    visible: true,
    recommended: Boolean(model.recommended),
    schema: model.schema,
  };
}

function normalizeTier(value: string): PlatformModel["tier"] {
  const normalized = value.trim().toLowerCase();
  if (normalized === "lite") return "Lite";
  if (normalized === "standard") return "Standard";
  if (normalized === "ultra") return "Ultra";
  return "Pro";
}

function mergeSavedModel(current: PlatformModel | null, saved: { id: string; schema?: SchemaField[] }, draft: ModelDraft): PlatformModel {
  const template = current ?? localPlatformModels.find((model) => model.modality === draft.modality) ?? localPlatformModels[0];
  return {
    ...template,
    id: draft.id,
    name: draft.name,
    displayName: draft.name,
    shortName: draft.shortName || draft.name,
    modality: draft.modality,
    tier: draft.tier,
    description: draft.description,
    useCases: splitList(draft.useCasesText),
    price: draft.price,
    eta: draft.eta,
    recommended: draft.recommended,
    schema: saved.schema ?? draft.schema,
  };
}

function splitList(value: string) {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
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

function SelectField({ label, options, value, onChange }: { label: string; options: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-black text-slate-500">{label}</span>
      <select
        className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <button
      className={cn(
        "h-11 rounded-xl px-4 text-sm font-black transition",
        value ? "bg-slate-950 text-white" : "bg-white text-slate-500 ring-1 ring-slate-200 hover:text-slate-950",
      )}
      type="button"
      onClick={() => onChange(!value)}
    >
      {label}: {value ? "On" : "Off"}
    </button>
  );
}
