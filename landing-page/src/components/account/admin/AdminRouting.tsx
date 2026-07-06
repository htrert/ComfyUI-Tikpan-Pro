import { GitBranch, Loader2, Save, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  listRemoteChannels,
  updateRemoteChannel,
  upsertRemoteChannelMapping,
  type ChannelMappingUpsert,
  type ChannelPatch,
} from "../../../apiClient";
import type { Channel } from "../../../productData";
import { cn } from "../../../lib";
import { GlassCard } from "../../GlassCard";

type ChannelDraft = {
  status: Channel["status"];
  role: Channel["role"];
  weight: string;
  costPrice: string;
  salePrice: string;
};

type MappingDraft = {
  platform: string;
  upstream: string;
  transform: ChannelMappingUpsert["transform"];
  defaultValue: string;
  note: string;
};

const channelStatuses: Channel["status"][] = ["active", "degraded", "disabled"];
const channelRoles: Channel["role"][] = ["primary", "backup", "cheap", "fast", "quality"];
const mappingTransforms: ChannelMappingUpsert["transform"][] = ["direct", "map", "default", "omit", "template"];

export function AdminRouting() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState("");
  const [channelDraft, setChannelDraft] = useState<ChannelDraft | null>(null);
  const [mappingDrafts, setMappingDrafts] = useState<MappingDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingChannel, setSavingChannel] = useState(false);
  const [savingMappings, setSavingMappings] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadChannels() {
      try {
        setLoading(true);
        const remoteChannels = await listRemoteChannels();
        if (cancelled) return;
        setChannels(remoteChannels);
        setSelectedChannelId((current) => current || remoteChannels[0]?.id || "");
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Channel admin API is unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadChannels();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedChannel = useMemo(
    () => channels.find((channel) => channel.id === selectedChannelId) ?? channels[0] ?? null,
    [channels, selectedChannelId],
  );

  useEffect(() => {
    if (!selectedChannel) {
      setChannelDraft(null);
      setMappingDrafts([]);
      return;
    }

    setChannelDraft(channelToDraft(selectedChannel));
    setMappingDrafts(channelToMappingDrafts(selectedChannel));
  }, [selectedChannel]);

  async function saveChannel() {
    if (!selectedChannel || !channelDraft) return;

    const patch: ChannelPatch = {
      status: channelDraft.status,
      role: channelDraft.role,
      weight: toNumber(channelDraft.weight),
      cost_price: toNumber(channelDraft.costPrice),
      sale_price: toNumber(channelDraft.salePrice),
    };

    try {
      setSavingChannel(true);
      const saved = await updateRemoteChannel(selectedChannel.id, patch);
      replaceChannel(saved);
      setMessage(`Saved channel ${saved.id}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Channel save failed.");
    } finally {
      setSavingChannel(false);
    }
  }

  async function saveMappings() {
    if (!selectedChannel) return;

    try {
      setSavingMappings(true);
      let latest = selectedChannel;
      for (const draft of mappingDrafts) {
        const payload: ChannelMappingUpsert = {
          platform_param_key: draft.platform,
          upstream_param_key: draft.transform === "omit" ? null : draft.upstream || draft.platform,
          transform: draft.transform,
          default_value: parseDefaultValue(draft.defaultValue),
          note: draft.note || null,
        };
        latest = await upsertRemoteChannelMapping(selectedChannel.id, payload);
      }
      replaceChannel(latest);
      setMessage(`Saved ${mappingDrafts.length} mapping${mappingDrafts.length === 1 ? "" : "s"} for ${latest.id}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Parameter mapping save failed.");
    } finally {
      setSavingMappings(false);
    }
  }

  function replaceChannel(nextChannel: Channel) {
    setChannels((current) => current.map((channel) => (channel.id === nextChannel.id ? nextChannel : channel)));
    setSelectedChannelId(nextChannel.id);
  }

  function updateMapping(index: number, patch: Partial<MappingDraft>) {
    setMappingDrafts((current) => current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, ...patch } : draft)));
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Routing and mappings</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Channel parameter routing</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              Configure live channel status, weights, pricing, and platform-to-upstream parameter mappings.
            </p>
          </div>
          {loading && (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-black text-slate-500 shadow-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading
            </span>
          )}
        </div>
        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <GlassCard className="p-4">
          <p className="mb-3 text-sm font-black text-slate-950">Channels</p>
          <div className="grid gap-2">
            {channels.map((channel) => (
              <button
                key={channel.id}
                className={cn(
                  "rounded-2xl border p-3 text-left transition",
                  selectedChannel?.id === channel.id ? "border-teal-300 bg-teal-50/80" : "border-slate-200 bg-white/80 hover:border-slate-300",
                )}
                type="button"
                onClick={() => setSelectedChannelId(channel.id)}
              >
                <p className="truncate text-sm font-black text-slate-950">{channel.id}</p>
                <p className="mt-1 truncate text-xs font-bold text-slate-500">{channel.platformModelId}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-black text-slate-500">{channel.role}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-black text-slate-500">{channel.status}</span>
                </div>
              </button>
            ))}
            {channels.length === 0 && <p className="rounded-xl bg-white/78 px-3 py-8 text-center text-sm font-bold text-slate-400">No channels</p>}
          </div>
        </GlassCard>

        <div className="grid min-w-0 gap-4">
          {selectedChannel && channelDraft && (
            <GlassCard className="p-5">
              <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700">
                    <GitBranch className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="break-words font-black text-slate-950">{selectedChannel.providerModel}</p>
                    <p className="mt-1 text-sm font-semibold leading-6 text-slate-500">
                      {selectedChannel.platformModelId} through {selectedChannel.providerId}
                    </p>
                  </div>
                </div>
                <button
                  className="inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={savingChannel}
                  type="button"
                  onClick={() => void saveChannel()}
                >
                  {savingChannel ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save channel
                </button>
              </div>

              <div className="grid gap-4 lg:grid-cols-5">
                <SelectField
                  label="Status"
                  options={channelStatuses}
                  value={channelDraft.status}
                  onChange={(value) => setChannelDraft({ ...channelDraft, status: value as Channel["status"] })}
                />
                <SelectField
                  label="Role"
                  options={channelRoles}
                  value={channelDraft.role}
                  onChange={(value) => setChannelDraft({ ...channelDraft, role: value as Channel["role"] })}
                />
                <Field label="Weight" value={channelDraft.weight} onChange={(value) => setChannelDraft({ ...channelDraft, weight: value })} />
                <Field label="Cost price" value={channelDraft.costPrice} onChange={(value) => setChannelDraft({ ...channelDraft, costPrice: value })} />
                <Field label="Sale price" value={channelDraft.salePrice} onChange={(value) => setChannelDraft({ ...channelDraft, salePrice: value })} />
              </div>
            </GlassCard>
          )}

          {selectedChannel && (
            <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
              <GlassCard className="p-5">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-lg font-black text-slate-950">Parameter mappings</p>
                    <p className="mt-1 text-sm font-semibold text-slate-500">Save rows into the live channel parameter mapping table.</p>
                  </div>
                  <button
                    className="inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    disabled={savingMappings || mappingDrafts.length === 0}
                    type="button"
                    onClick={() => void saveMappings()}
                  >
                    {savingMappings ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save mappings
                  </button>
                </div>

                <div className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
                  <div className="hidden grid-cols-[0.9fr_0.9fr_0.7fr_0.8fr_1fr] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
                    <span>Platform param</span>
                    <span>Upstream param</span>
                    <span>Transform</span>
                    <span>Default</span>
                    <span>Note</span>
                  </div>
                  {mappingDrafts.map((mapping, index) => (
                    <div key={`${mapping.platform}-${index}`} className="grid gap-2 border-t border-slate-100 px-4 py-3 md:grid-cols-[0.9fr_0.9fr_0.7fr_0.8fr_1fr] md:items-center">
                      <span className="font-mono text-sm font-black text-slate-900">{mapping.platform}</span>
                      <input
                        className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
                        disabled={mapping.transform === "omit"}
                        value={mapping.upstream}
                        onChange={(event) => updateMapping(index, { upstream: event.target.value })}
                      />
                      <select
                        className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-black text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
                        value={mapping.transform}
                        onChange={(event) => updateMapping(index, { transform: event.target.value as ChannelMappingUpsert["transform"] })}
                      >
                        {mappingTransforms.map((transform) => (
                          <option key={transform} value={transform}>
                            {transform}
                          </option>
                        ))}
                      </select>
                      <input
                        className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
                        value={mapping.defaultValue}
                        onChange={(event) => updateMapping(index, { defaultValue: event.target.value })}
                      />
                      <input
                        className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
                        value={mapping.note}
                        onChange={(event) => updateMapping(index, { note: event.target.value })}
                      />
                    </div>
                  ))}
                  {mappingDrafts.length === 0 && <p className="px-4 py-10 text-center text-sm font-bold text-slate-400">No mappable parameters</p>}
                </div>
              </GlassCard>

              <GlassCard className="p-5">
                <div className="flex items-center gap-2">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
                    <ShieldCheck className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-lg font-black text-slate-950">Channel diagnostics</p>
                    <p className="text-sm font-semibold text-slate-500">Read-only routing facts from the backend.</p>
                  </div>
                </div>

                <div className="mt-4 grid gap-3">
                  <Info label="Provider" value={selectedChannel.providerId} />
                  <Info label="Platform model" value={selectedChannel.platformModelId} />
                  <Info label="Upstream model" value={selectedChannel.providerModel} />
                  <Info label="Latency" value={`${selectedChannel.latency} ms`} />
                  <Info label="Success rate" value={`${selectedChannel.successRate}%`} />
                  <Info label="Supports" value={selectedChannel.supports.join(", ") || "-"} />
                </div>
              </GlassCard>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function channelToDraft(channel: Channel): ChannelDraft {
  return {
    status: channel.status,
    role: channel.role,
    weight: String(channel.weight),
    costPrice: channel.cost,
    salePrice: channel.sale,
  };
}

function channelToMappingDrafts(channel: Channel): MappingDraft[] {
  const editableKeys = new Set(channel.supports);
  const editableMappings = editableKeys.size > 0 ? channel.paramMap.filter((mapping) => editableKeys.has(mapping.platform)) : channel.paramMap;
  const mappedKeys = new Set(editableMappings.map((mapping) => mapping.platform));
  const existingRows = editableMappings.map((mapping) => ({
    platform: mapping.platform,
    upstream: mapping.upstream,
    transform: mapping.transform,
    defaultValue: stringifyDefaultValue(mapping.defaultValue),
    note: mapping.note ?? "",
  }));
  const missingRows = channel.supports
    .filter((key) => !mappedKeys.has(key))
    .map((key) => ({
      platform: key,
      upstream: key,
      transform: "direct" as const,
      defaultValue: "",
      note: "",
    }));
  return [...existingRows, ...missingRows];
}

function parseDefaultValue(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  const parsedNumber = Number(trimmed);
  if (Number.isFinite(parsedNumber) && trimmed === String(parsedNumber)) return parsedNumber;
  return trimmed;
}

function stringifyDefaultValue(value: unknown) {
  if (value === undefined || value === null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function toNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
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

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200/70 bg-white/78 p-3">
      <p className="text-xs font-black text-slate-400">{label}</p>
      <p className="mt-1 break-words font-mono text-xs font-bold leading-5 text-slate-700">{value}</p>
    </div>
  );
}
