import { ArrowRight, Snowflake, WalletCards } from "lucide-react";
import type { ReactNode } from "react";
import { ledgerItems } from "../../appData";
import type { AppRoute, UserProfile } from "../../types";
import { formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

export function AccountAssets({
  user,
  onNavigate,
}: {
  user: UserProfile;
  onNavigate: (route: AppRoute) => void;
}) {
  return (
    <div className="grid gap-4">
      <GlassCard className="p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm font-black text-teal-700">我的资产</p>
            <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">{formatTokens(user.tokens)}</h1>
            <p className="mt-2 text-sm font-semibold text-slate-500">当前套餐：{user.plan}</p>
          </div>
          <button className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-600" type="button">
            <WalletCards className="h-4 w-4" />
            充值 Tokens
          </button>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <AssetMetric label="月度额度" value={formatTokens(user.monthlyAllowance)} />
          <AssetMetric label="冻结中" value={formatTokens(user.frozenTokens)} icon={<Snowflake className="h-4 w-4 text-sky-500" />} />
          <AssetMetric label="可继续创作" value="48 次轻量任务" />
        </div>
      </GlassCard>

      <GlassCard className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-lg font-black text-slate-950">近期流水</p>
            <p className="mt-1 text-sm font-semibold text-slate-500">失败或取消的任务会自动退回冻结 Tokens。</p>
          </div>
          <button className="hidden items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-black text-slate-600 shadow-sm sm:inline-flex" type="button" onClick={() => onNavigate("workspace")}>
            去创作
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200/70 bg-white/72">
          {ledgerItems.map((item) => (
            <div key={item.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:grid-cols-[1fr_auto_auto] sm:items-center">
              <div>
                <p className="text-sm font-black text-slate-900">{item.title}</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">{item.time}</p>
              </div>
              <span className="text-sm font-black text-slate-700">{item.tokens > 0 ? "+" : ""}{formatTokens(item.tokens)}</span>
              <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{item.status}</span>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
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
