import { ArrowLeft, LockKeyhole, ShieldCheck } from "lucide-react";
import type { AccountSection, AppRoute } from "../../types";
import { GlassCard } from "../GlassCard";

export function AdminPlaceholder({
  isAdmin,
  onNavigate,
}: {
  isAdmin: boolean;
  onNavigate: (route: AppRoute, section?: AccountSection) => void;
}) {
  if (!isAdmin) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f8faf7] px-4">
        <GlassCard className="max-w-lg p-6 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-950 text-white">
            <LockKeyhole className="h-6 w-6" />
          </span>
          <h1 className="mt-5 text-2xl font-black tracking-normal text-slate-950">仅管理员可见</h1>
          <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">普通创作者前台不会显示管理入口。</p>
          <button
            className="mt-6 inline-flex h-11 items-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-600"
            type="button"
            onClick={() => onNavigate("workspace")}
          >
            <ArrowLeft className="h-4 w-4" />
            返回工作台
          </button>
        </GlassCard>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8faf7] px-4 py-6 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <button className="mb-4 inline-flex h-10 items-center gap-2 rounded-full bg-white px-4 text-sm font-black text-slate-600 shadow-sm" type="button" onClick={() => onNavigate("workspace")}>
          <ArrowLeft className="h-4 w-4" />
          返回前台
        </button>
        <GlassCard className="p-6">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-950 text-white">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-black text-teal-700">平台管理后台</p>
              <h1 className="text-3xl font-black tracking-normal text-slate-950">内部供应链配置</h1>
            </div>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {["上游供应商", "平台模型", "渠道配置", "参数映射", "路由策略", "Tokens 定价", "用户订单", "任务日志", "系统公告"].map((item) => (
              <div key={item} className="rounded-2xl border border-slate-200/70 bg-white/78 p-4 text-sm font-black text-slate-800 shadow-sm">{item}</div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
