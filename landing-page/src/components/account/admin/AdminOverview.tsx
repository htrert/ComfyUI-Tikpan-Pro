import { Activity, Database, Image, Loader2, ServerCog, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  getRemoteCommercialReadiness,
  listRemoteChannels,
  listRemotePlatformModels,
  listRemoteProviders,
  type CommercialReadinessSummary,
} from "../../../apiClient";
import { platformModels as localPlatformModels, type Channel, type PlatformModel, type Provider } from "../../../productData";
import { GlassCard } from "../../GlassCard";

type AdminOverviewState = {
  models: PlatformModel[];
  providers: Provider[];
  channels: Channel[];
  readiness: CommercialReadinessSummary | null;
};

const emptyState: AdminOverviewState = {
  models: [],
  providers: [],
  channels: [],
  readiness: null,
};

export function AdminOverview() {
  const [state, setState] = useState<AdminOverviewState>(emptyState);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadAdminOverview() {
      try {
        setLoading(true);
        const [models, providers, channels, readiness] = await Promise.all([
          listRemotePlatformModels(localPlatformModels),
          listRemoteProviders(),
          listRemoteChannels(),
          getRemoteCommercialReadiness().catch(() => null),
        ]);
        if (cancelled) return;
        setState({ models, providers, channels, readiness });
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setState(emptyState);
        setMessage(error instanceof Error ? error.message : "Admin APIs are unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadAdminOverview();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeChannels = state.channels.filter((channel) => channel.status === "active");
  const routingChain = useMemo(() => {
    const channel = activeChannels[0] ?? state.channels[0];
    const model = state.models.find((item) => item.id === channel?.platformModelId);
    const provider = state.providers.find((item) => item.id === channel?.providerId);
    return { channel, model, provider };
  }, [activeChannels, state.channels, state.models, state.providers]);

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Admin overview</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Model and provider control plane</h1>
            <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
              Live catalog, provider, channel, and pricing readiness data from the backend admin APIs.
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

      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={Image} label="Visible models" value={String(state.models.length)} />
        <Metric icon={ServerCog} label="Providers" value={String(state.providers.length)} />
        <Metric icon={SlidersHorizontal} label="Active channels" value={String(activeChannels.length)} />
        <Metric
          icon={Database}
          label="Avg margin"
          value={state.readiness ? `${Math.round(state.readiness.summary.average_gross_margin * 100)}%` : "-"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <GlassCard className="p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <Activity className="h-4 w-4" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">Current routing chain</p>
              <p className="text-sm font-semibold text-slate-500">First active channel selected from the live admin catalog.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-4">
            {[
              routingChain.model?.modality ?? "No modality",
              routingChain.model?.id ?? "No model",
              routingChain.provider?.id ?? "No provider",
              routingChain.channel?.providerModel ?? "No upstream model",
            ].map((item, index) => (
              <div key={`${index}-${item}`} className="rounded-2xl border border-slate-200/70 bg-white/78 p-4">
                <p className="text-xs font-black text-slate-400">Step {index + 1}</p>
                <p className="mt-2 break-words text-sm font-black text-slate-900">{item}</p>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <p className="text-lg font-black text-slate-950">Commercial readiness</p>
          <div className="mt-4 grid gap-2">
            <ReadinessRow label="Sellable" value={state.readiness?.summary.sellable_models ?? 0} />
            <ReadinessRow label="Watch" value={state.readiness?.summary.watch_models ?? 0} />
            <ReadinessRow label="Blocked" value={state.readiness?.summary.blocked_models ?? 0} />
          </div>
          <div className="mt-4 grid gap-2">
            {(state.readiness?.priority_actions ?? []).slice(0, 3).map((item) => (
              <div key={`${item.model_id}-${item.action}`} className="rounded-xl bg-white/78 px-3 py-2">
                <p className="text-xs font-black text-slate-900">{item.model_name}</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">{item.action}</p>
              </div>
            ))}
            {state.readiness && state.readiness.priority_actions.length === 0 && (
              <p className="rounded-xl bg-white/78 px-3 py-4 text-center text-sm font-bold text-slate-400">No priority actions</p>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof ServerCog; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/70 bg-white/82 p-4 shadow-sm">
      <Icon className="h-5 w-5 text-violet-700" />
      <p className="mt-4 text-xs font-black text-slate-400">{label}</p>
      <p className="mt-1 truncate text-lg font-black text-slate-950">{value}</p>
    </div>
  );
}

function ReadinessRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-white/78 px-3 py-2">
      <span className="text-xs font-black text-slate-500">{label}</span>
      <span className="text-sm font-black text-slate-950">{value}</span>
    </div>
  );
}
