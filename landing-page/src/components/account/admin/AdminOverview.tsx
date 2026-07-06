import { Database, Image, ServerCog, SlidersHorizontal } from "lucide-react";
import { adminParameters, adminPlatformModel, adminProvider } from "../../../adminData";
import { GlassCard } from "../../GlassCard";

export function AdminOverview() {
  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <p className="text-sm font-black text-teal-700">管理概览</p>
        <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">模型供应配置</h1>
        <p className="mt-2 text-sm font-semibold leading-6 text-slate-500">
          管理员和普通用户使用同一套账号入口；管理员在账户中心多看到这些配置项。
        </p>
      </GlassCard>

      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={ServerCog} label="供应商" value={adminProvider.name} />
        <Metric icon={Image} label="当前模型" value={adminPlatformModel.name} />
        <Metric icon={SlidersHorizontal} label="模型参数" value={`${adminParameters.length} 个`} />
        <Metric icon={Database} label="调用方式" value="异步轮询" />
      </div>

      <GlassCard className="p-5">
        <p className="text-lg font-black text-slate-950">当前链路</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          {[
            "图片模型",
            adminPlatformModel.id,
            adminProvider.id,
            adminPlatformModel.upstreamModelId,
          ].map((item, index) => (
            <div key={item} className="rounded-2xl border border-slate-200/70 bg-white/78 p-4">
              <p className="text-xs font-black text-slate-400">Step {index + 1}</p>
              <p className="mt-2 break-words text-sm font-black text-slate-900">{item}</p>
            </div>
          ))}
        </div>
      </GlassCard>
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
