import { Check, Loader2, Play, Plus, Trash2, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  deleteRemotePreset,
  listRemotePresets,
  saveRemotePreset,
  useRemotePreset,
  type CreativePreset,
  type CreativePresetInput,
} from "../../apiClient";
import type { RouteMode } from "../../productData";
import { GlassCard } from "../GlassCard";

const defaultModel = "tikpan.image.gpt-image-2-4k";
const routeModes: RouteMode[] = ["balanced", "quality", "fast", "cheap", "stable"];

export function AccountPresets() {
  const [presets, setPresets] = useState<CreativePreset[]>([]);
  const [name, setName] = useState("Product hero image");
  const [description, setDescription] = useState("Clean commerce visual preset with a square image output.");
  const [prompt, setPrompt] = useState("Bright premium product image, clean background, natural light, crisp details.");
  const [size, setSize] = useState("1024x1024");
  const [quality, setQuality] = useState("auto");
  const [routeMode, setRouteMode] = useState<RouteMode>("balanced");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadPresets() {
      try {
        setLoading(true);
        const remotePresets = await listRemotePresets(50);
        if (cancelled) return;
        setPresets(remotePresets);
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Preset API is unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadPresets();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalUses = useMemo(() => presets.reduce((sum, preset) => sum + preset.usage_count, 0), [presets]);

  async function createPreset() {
    const input: CreativePresetInput = {
      name: name.trim(),
      description: description.trim(),
      model: defaultModel,
      route_mode: routeMode,
      input: {
        prompt: prompt.trim(),
        size,
        quality,
        n: 1,
        background: "opaque",
        output_format: "png",
      },
    };

    if (!input.name || !input.input.prompt) {
      setMessage("Preset name and prompt are required.");
      return;
    }

    try {
      setSaving(true);
      const preset = await saveRemotePreset(input);
      setPresets((current) => [preset, ...current.filter((item) => item.id !== preset.id)]);
      setMessage(`Created preset ${preset.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Preset creation failed.");
    } finally {
      setSaving(false);
    }
  }

  async function usePreset(presetId: string) {
    try {
      setSaving(true);
      const preset = await useRemotePreset(presetId);
      setPresets((current) => current.map((item) => (item.id === preset.id ? preset : item)));
      setMessage(`Used preset ${preset.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Preset use failed.");
    } finally {
      setSaving(false);
    }
  }

  async function deletePreset(presetId: string) {
    try {
      setSaving(true);
      await deleteRemotePreset(presetId);
      setPresets((current) => current.filter((preset) => preset.id !== presetId));
      setMessage("Preset deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Preset delete failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Creative presets</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Reusable generation kits</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold text-slate-500">
              Save model, routing mode, and common input parameters so repeated work starts from a clean preset.
            </p>
          </div>
          {loading && (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-black text-slate-500 shadow-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading
            </span>
          )}
        </div>

        <div className="mt-5 grid gap-3 rounded-2xl border border-slate-200/70 bg-white/78 p-4 xl:grid-cols-[1fr_0.8fr_0.6fr_auto] xl:items-end">
          <label className="grid gap-2 xl:col-span-2">
            <span className="text-xs font-black text-slate-500">Preset name</span>
            <input
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-black text-slate-500">Route mode</span>
            <select
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={routeMode}
              onChange={(event) => setRouteMode(event.target.value as RouteMode)}
            >
              {routeModes.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </select>
          </label>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={saving}
            type="button"
            onClick={() => void createPreset()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create preset
          </button>
          <label className="grid gap-2 xl:col-span-2">
            <span className="text-xs font-black text-slate-500">Description</span>
            <input
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-black text-slate-500">Size</span>
            <select
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={size}
              onChange={(event) => setSize(event.target.value)}
            >
              {["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "3840x2160"].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-black text-slate-500">Quality</span>
            <select
              className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={quality}
              onChange={(event) => setQuality(event.target.value)}
            >
              {["auto", "low", "medium", "high"].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-2 xl:col-span-4">
            <span className="text-xs font-black text-slate-500">Prompt</span>
            <textarea
              className="min-h-24 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-sm font-bold leading-6 text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
            />
          </label>
        </div>

        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}
      </GlassCard>

      <GlassCard className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <WandSparkles className="h-5 w-5" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">Saved presets</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">{presets.length} presets · {totalUses} total uses</p>
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {presets.map((preset) => (
            <article key={preset.id} className="rounded-2xl border border-slate-200/70 bg-white/82 p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black text-slate-950">{preset.name}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-500">{preset.model} · {preset.route_mode}</p>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-500">
                  <Check className="h-3.5 w-3.5 text-teal-600" />
                  {preset.usage_count}
                </span>
              </div>
              <p className="mt-3 line-clamp-2 text-sm font-semibold leading-6 text-slate-500">{preset.description || String(preset.input.prompt ?? "")}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(preset.input).slice(0, 5).map(([key, value]) => (
                  <span key={key} className="rounded-full bg-slate-50 px-2.5 py-1 text-[11px] font-black text-slate-500">
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="inline-flex h-9 items-center gap-1.5 rounded-full bg-slate-950 px-3 text-xs font-black text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={saving}
                  type="button"
                  onClick={() => void usePreset(preset.id)}
                >
                  <Play className="h-3.5 w-3.5" />
                  Use
                </button>
                <button
                  className="inline-flex h-9 items-center gap-1.5 rounded-full bg-slate-100 px-3 text-xs font-black text-slate-600 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={saving}
                  type="button"
                  onClick={() => void deletePreset(preset.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            </article>
          ))}
          {!loading && presets.length === 0 && <p className="rounded-2xl bg-white/78 px-4 py-10 text-center text-sm font-bold text-slate-400">No presets yet</p>}
        </div>
      </GlassCard>
    </div>
  );
}
