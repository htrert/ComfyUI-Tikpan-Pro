import { ArrowRight, Loader2, Plus, Snowflake, WalletCards } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  getRemoteWallet,
  listUserRemoteTasks,
  topUpRemoteWallet,
  type RemoteTaskRecord,
  type WalletLedgerItem,
  type WalletSnapshot,
} from "../../apiClient";
import type { AppRoute, UserProfile } from "../../types";
import { formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

type WalletState = {
  wallet: WalletSnapshot;
  ledger: WalletLedgerItem[];
};

export function AccountAssets({
  user,
  onNavigate,
}: {
  user: UserProfile;
  onNavigate: (route: AppRoute) => void;
}) {
  const [walletState, setWalletState] = useState<WalletState>(() => fallbackWalletState(user));
  const [tasks, setTasks] = useState<RemoteTaskRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadAccountActivity() {
      try {
        setLoading(true);
        const [remoteWallet, remoteTasks] = await Promise.all([getRemoteWallet(), listUserRemoteTasks(8)]);
        if (cancelled) return;
        setWalletState(remoteWallet);
        setTasks(remoteTasks);
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Wallet API is unavailable. Showing local account values.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadAccountActivity();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const activeTasks = useMemo(() => tasks.filter((task) => ["queued", "running", "saving_media"].includes(task.status)), [tasks]);

  async function addDemoTokens() {
    try {
      setSaving(true);
      const remoteWallet = await topUpRemoteWallet(10);
      setWalletState(remoteWallet);
      setMessage("Added 10 demo Tokens to the wallet.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Top-up failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <GlassCard className="p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">Wallet & tasks</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">{formatTokens(walletState.wallet.available)}</h1>
            <p className="mt-2 text-sm font-semibold text-slate-500">
              Plan {user.plan}. Balance updates as tasks freeze, settle, release, or refund Tokens.
            </p>
          </div>
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={saving}
            type="button"
            onClick={() => void addDemoTokens()}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add demo Tokens
          </button>
        </div>

        {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}

        <div className="mt-6 grid gap-3 sm:grid-cols-4">
          <AssetMetric label="Balance" value={formatTokens(walletState.wallet.balance)} />
          <AssetMetric label="Frozen" value={formatTokens(walletState.wallet.frozen)} icon={<Snowflake className="h-4 w-4 text-sky-500" />} />
          <AssetMetric label="Available" value={formatTokens(walletState.wallet.available)} />
          <AssetMetric label="Active tasks" value={String(activeTasks.length)} />
        </div>
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <GlassCard className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-lg font-black text-slate-950">Recent task spend</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">Generated tasks keep their status, project, and estimated cost visible here.</p>
            </div>
            <button
              className="hidden items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-black text-slate-600 shadow-sm sm:inline-flex"
              type="button"
              onClick={() => onNavigate("workspace")}
            >
              Create
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 overflow-hidden rounded-xl border border-slate-200/70 bg-white/72">
            {loading ? (
              <div className="grid place-items-center px-4 py-10 text-sm font-bold text-slate-400">
                <Loader2 className="mb-2 h-4 w-4 animate-spin" />
                Loading account activity
              </div>
            ) : tasks.length > 0 ? (
              tasks.map((task) => (
                <div key={task.task_id} className="grid gap-2 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:grid-cols-[1fr_auto_auto] sm:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-slate-900">{String(task.input?.prompt ?? task.input?.message ?? task.task_id)}</p>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                      {task.model}
                      {task.project_name ? ` · ${task.project_name}` : ""}
                    </p>
                  </div>
                  <span className="text-sm font-black text-slate-700">{formatTokens(Number(task.final_cost ?? task.estimated_cost ?? 0))}</span>
                  <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{task.status}</span>
                </div>
              ))
            ) : (
              <p className="px-4 py-10 text-center text-sm font-bold text-slate-400">No tasks yet</p>
            )}
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <WalletCards className="h-5 w-5" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">Wallet ledger</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">Freeze, settlement, release, and top-up events.</p>
            </div>
          </div>

          <div className="mt-4 overflow-hidden rounded-xl border border-slate-200/70 bg-white/72">
            {walletState.ledger.length > 0 ? (
              walletState.ledger.map((item) => (
                <div key={item.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:grid-cols-[1fr_auto] sm:items-center">
                  <div>
                    <p className="text-sm font-black text-slate-900">{ledgerTitle(item)}</p>
                    <p className="mt-1 text-xs font-semibold text-slate-500">{formatDateTime(item.created_at)}</p>
                  </div>
                  <span className="text-sm font-black text-slate-700">
                    {Number(item.amount) > 0 ? "+" : ""}
                    {formatTokens(Number(item.amount))}
                  </span>
                </div>
              ))
            ) : (
              <p className="px-4 py-10 text-center text-sm font-bold text-slate-400">No ledger entries yet</p>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function fallbackWalletState(user: UserProfile): WalletState {
  return {
    wallet: {
      user_id: "demo_user",
      currency: "TOKENS",
      balance: user.tokens,
      frozen: user.frozenTokens,
      available: Math.max(0, user.tokens - user.frozenTokens),
      updated_at: new Date().toISOString(),
    },
    ledger: [],
  };
}

function ledgerTitle(item: WalletLedgerItem) {
  const labels: Record<WalletLedgerItem["type"], string> = {
    top_up: "Top-up",
    gift: "Gift",
    pre_authorize: "Task freeze",
    settle: "Task settlement",
    release: "Task release",
    refund: "Refund",
    admin_adjust: "Admin adjustment",
  };
  return item.note || labels[item.type] || item.type;
}

function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function AssetMetric({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200/70 bg-white/72 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-black text-slate-400">{label}</p>
        {icon}
      </div>
      <p className="mt-2 text-lg font-black text-slate-950">{value}</p>
    </div>
  );
}
