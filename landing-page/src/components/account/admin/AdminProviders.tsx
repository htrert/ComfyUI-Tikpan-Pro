import { KeyRound, Loader2, Save, ServerCog } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  listRemoteProviderModels,
  listRemoteProviders,
  upsertRemoteProvider,
  upsertRemoteProviderModel,
  type ProviderModelUpsert,
  type ProviderUpsert,
} from "../../../apiClient";
import type { Modality, Provider, ProviderModel } from "../../../productData";
import { cn } from "../../../lib";
import { GlassCard } from "../../GlassCard";

const providerKinds: Provider["kind"][] = ["official", "relay", "private"];
const providerStatuses: Provider["status"][] = ["active", "degraded", "testing", "disabled"];
const modalities: Modality[] = ["image", "video", "chat", "audio", "workflow"];

type ProviderDraft = {
  id: string;
  name: string;
  kind: Provider["kind"];
  status: Provider["status"];
  baseUrl: string;
  authType: ProviderUpsert["auth_type"];
  rpm: string;
  concurrency: string;
  latencyMs: string;
  successRate: string;
};

type ProviderModelDraft = {
  id: string;
  providerId: string;
  upstreamModelName: string;
  endpointType: string;
  modality: Modality;
  status: ProviderModel["status"];
  notes: string;
};

export function AdminProviders() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerModels, setProviderModels] = useState<ProviderModel[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [selectedProviderModelId, setSelectedProviderModelId] = useState("");
  const [providerDraft, setProviderDraft] = useState<ProviderDraft | null>(null);
  const [providerModelDraft, setProviderModelDraft] = useState<ProviderModelDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState(false);
  const [savingProviderModel, setSavingProviderModel] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadProviders() {
      try {
        setLoading(true);
        const [remoteProviders, remoteProviderModels] = await Promise.all([listRemoteProviders(), listRemoteProviderModels()]);
        if (cancelled) return;
        setProviders(remoteProviders);
        setProviderModels(remoteProviderModels);
        setSelectedProviderId((current) => current || remoteProviders[0]?.id || "");
        setSelectedProviderModelId((current) => current || remoteProviderModels[0]?.id || "");
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Provider admin APIs are unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadProviders();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedProviderId) ?? providers[0] ?? null,
    [providers, selectedProviderId],
  );
  const filteredProviderModels = useMemo(
    () => providerModels.filter((model) => !selectedProvider?.id || model.providerId === selectedProvider.id),
    [providerModels, selectedProvider],
  );
  const selectedProviderModel = useMemo(
    () =>
      filteredProviderModels.find((model) => model.id === selectedProviderModelId) ??
      filteredProviderModels[0] ??
      providerModels[0] ??
      null,
    [filteredProviderModels, providerModels, selectedProviderModelId],
  );

  useEffect(() => {
    if (!selectedProvider) {
      setProviderDraft(null);
      return;
    }
    setProviderDraft(providerToDraft(selectedProvider));
  }, [selectedProvider]);

  useEffect(() => {
    if (!selectedProviderModel) {
      setProviderModelDraft(null);
      return;
    }
    setSelectedProviderModelId(selectedProviderModel.id);
    setProviderModelDraft(providerModelToDraft(selectedProviderModel));
  }, [selectedProviderModel]);

  async function saveProvider() {
    if (!providerDraft) return;

    const input: ProviderUpsert = {
      id: providerDraft.id,
      name: providerDraft.name,
      kind: providerDraft.kind,
      status: providerDraft.status,
      base_url: providerDraft.baseUrl,
      auth_type: providerDraft.authType,
      rpm: toNumber(providerDraft.rpm),
      concurrency: toNumber(providerDraft.concurrency),
      latency_ms: toNumber(providerDraft.latencyMs),
      success_rate: toNumber(providerDraft.successRate),
    };

    try {
      setSavingProvider(true);
      const saved = await upsertRemoteProvider(input, providerDraft.id);
      setProviders((current) => current.map((provider) => (provider.id === saved.id ? saved : provider)));
      setMessage(`Saved provider ${saved.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Provider save failed.");
    } finally {
      setSavingProvider(false);
    }
  }

  async function saveProviderModel() {
    if (!providerModelDraft) return;

    const input: ProviderModelUpsert = {
      id: providerModelDraft.id,
      provider_id: providerModelDraft.providerId,
      upstream_model_name: providerModelDraft.upstreamModelName,
      endpoint_type: providerModelDraft.endpointType,
      modality: providerModelDraft.modality,
      status: providerModelDraft.status,
      raw_capabilities: {},
      notes: providerModelDraft.notes || null,
    };

    try {
      setSavingProviderModel(true);
      const saved = await upsertRemoteProviderModel(input, providerModelDraft.id);
      setProviderModels((current) => current.map((model) => (model.id === saved.id ? saved : model)));
      setMessage(`Saved upstream model ${saved.upstreamModelName}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Provider model save failed.");
    } finally {
      setSavingProviderModel(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Provider channels</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Upstream provider configuration</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              Manage live provider records and upstream model bindings used by routing channels.
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

      <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
        <GlassCard className="p-4">
          <p className="mb-3 text-sm font-black text-slate-950">Providers</p>
          <div className="grid gap-2">
            {providers.map((provider) => (
              <button
                key={provider.id}
                className={cn(
                  "rounded-2xl border p-3 text-left transition",
                  selectedProvider?.id === provider.id ? "border-teal-300 bg-teal-50/80" : "border-slate-200 bg-white/80 hover:border-slate-300",
                )}
                type="button"
                onClick={() => {
                  setSelectedProviderId(provider.id);
                  const firstModel = providerModels.find((model) => model.providerId === provider.id);
                  if (firstModel) setSelectedProviderModelId(firstModel.id);
                }}
              >
                <p className="truncate text-sm font-black text-slate-950">{provider.name}</p>
                <p className="mt-1 truncate text-xs font-bold text-slate-500">{provider.id}</p>
                <span className="mt-2 inline-flex rounded-full bg-white px-2 py-0.5 text-[11px] font-black text-slate-500">{provider.status}</span>
              </button>
            ))}
            {providers.length === 0 && <p className="rounded-xl bg-white/78 px-3 py-8 text-center text-sm font-bold text-slate-400">No providers</p>}
          </div>
        </GlassCard>

        <div className="grid min-w-0 gap-4">
          {providerDraft && (
            <GlassCard className="p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700">
                    <ServerCog className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-lg font-black text-slate-950">Provider record</p>
                    <p className="text-sm font-semibold text-slate-500">Base URL, status, health, and throttling.</p>
                  </div>
                </div>
                <button
                  className="inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={savingProvider}
                  type="button"
                  onClick={() => void saveProvider()}
                >
                  {savingProvider ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save provider
                </button>
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <Field label="Provider name" value={providerDraft.name} onChange={(value) => setProviderDraft({ ...providerDraft, name: value })} />
                <Field label="Provider ID" value={providerDraft.id} onChange={(value) => setProviderDraft({ ...providerDraft, id: value })} disabled />
                <SelectField
                  label="Kind"
                  options={providerKinds}
                  value={providerDraft.kind}
                  onChange={(value) => setProviderDraft({ ...providerDraft, kind: value as Provider["kind"] })}
                />
                <SelectField
                  label="Status"
                  options={providerStatuses}
                  value={providerDraft.status}
                  onChange={(value) => setProviderDraft({ ...providerDraft, status: value as Provider["status"] })}
                />
                <Field label="Base URL" value={providerDraft.baseUrl} onChange={(value) => setProviderDraft({ ...providerDraft, baseUrl: value })} />
                <SelectField
                  label="Auth type"
                  options={["bearer", "custom_header", "none"]}
                  value={providerDraft.authType}
                  onChange={(value) => setProviderDraft({ ...providerDraft, authType: value as ProviderUpsert["auth_type"] })}
                />
                <Field label="RPM" value={providerDraft.rpm} onChange={(value) => setProviderDraft({ ...providerDraft, rpm: value })} />
                <Field label="Concurrency" value={providerDraft.concurrency} onChange={(value) => setProviderDraft({ ...providerDraft, concurrency: value })} />
                <Field label="Latency ms" value={providerDraft.latencyMs} onChange={(value) => setProviderDraft({ ...providerDraft, latencyMs: value })} />
                <Field label="Success rate" value={providerDraft.successRate} onChange={(value) => setProviderDraft({ ...providerDraft, successRate: value })} />
              </div>
            </GlassCard>
          )}

          {providerModelDraft && (
            <GlassCard className="p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-slate-950">Upstream model</p>
                  <p className="text-sm font-semibold text-slate-500">Provider model records are bound to platform models through channels.</p>
                </div>
                <button
                  className="inline-flex h-10 items-center gap-2 rounded-full bg-violet-700 px-4 text-sm font-black text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={savingProviderModel}
                  type="button"
                  onClick={() => void saveProviderModel()}
                >
                  {savingProviderModel ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save upstream model
                </button>
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <label className="grid gap-2">
                  <span className="text-xs font-black text-slate-500">Provider model</span>
                  <select
                    className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                    value={providerModelDraft.id}
                    onChange={(event) => setSelectedProviderModelId(event.target.value)}
                  >
                    {filteredProviderModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.upstreamModelName}
                      </option>
                    ))}
                  </select>
                </label>
                <Field label="Upstream model name" value={providerModelDraft.upstreamModelName} onChange={(value) => setProviderModelDraft({ ...providerModelDraft, upstreamModelName: value })} />
                <Field label="Endpoint type" value={providerModelDraft.endpointType} onChange={(value) => setProviderModelDraft({ ...providerModelDraft, endpointType: value })} />
                <SelectField
                  label="Modality"
                  options={modalities}
                  value={providerModelDraft.modality}
                  onChange={(value) => setProviderModelDraft({ ...providerModelDraft, modality: value as Modality })}
                />
                <SelectField
                  label="Status"
                  options={providerStatuses}
                  value={providerModelDraft.status}
                  onChange={(value) => setProviderModelDraft({ ...providerModelDraft, status: value as ProviderModel["status"] })}
                />
                <Field label="Provider ID" value={providerModelDraft.providerId} onChange={(value) => setProviderModelDraft({ ...providerModelDraft, providerId: value })} disabled />
              </div>
              <label className="mt-4 grid gap-2">
                <span className="text-xs font-black text-slate-500">Notes</span>
                <textarea
                  className="min-h-20 rounded-xl border border-slate-200 bg-white/85 px-4 py-3 text-sm font-bold leading-6 text-slate-700 outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                  value={providerModelDraft.notes}
                  onChange={(event) => setProviderModelDraft({ ...providerModelDraft, notes: event.target.value })}
                />
              </label>
            </GlassCard>
          )}

          <GlassCard className="p-5">
            <div className="flex items-start gap-3">
              <KeyRound className="mt-0.5 h-5 w-5 text-amber-600" />
              <div>
                <p className="text-sm font-black text-amber-900">Provider keys stay server-side</p>
                <p className="mt-1 text-sm font-semibold leading-6 text-amber-800">
                  Use environment secrets or the provider-key admin API for credentials. This page only edits catalog and routing metadata.
                </p>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

function providerToDraft(provider: Provider): ProviderDraft {
  return {
    id: provider.id,
    name: provider.name,
    kind: provider.kind,
    status: provider.status,
    baseUrl: provider.baseUrl,
    authType: "bearer",
    rpm: String(provider.rpm),
    concurrency: String(provider.concurrency),
    latencyMs: String(provider.latency),
    successRate: String(provider.successRate),
  };
}

function providerModelToDraft(model: ProviderModel): ProviderModelDraft {
  return {
    id: model.id,
    providerId: model.providerId,
    upstreamModelName: model.upstreamModelName,
    endpointType: model.endpointType ?? "image_generation",
    modality: model.modality,
    status: model.status,
    notes: model.notes ?? "",
  };
}

function toNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function Field({
  disabled,
  label,
  value,
  onChange,
}: {
  disabled?: boolean;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-black text-slate-500">{label}</span>
      <input
        className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition disabled:bg-slate-100 disabled:text-slate-400 focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
        disabled={disabled}
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
        className="h-11 rounded-xl border border-slate-200 bg-white/85 px-3 text-sm font-bold text-slate-700 outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
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
