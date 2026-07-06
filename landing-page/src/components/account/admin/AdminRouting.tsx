import { GitBranch, Save, ShieldCheck } from "lucide-react";
import { adminParameters, adminPlatformModel, adminProvider } from "../../../adminData";
import { GlassCard } from "../../GlassCard";

export function AdminRouting() {
  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <p className="text-sm font-black text-teal-700">参数映射</p>
        <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">不同上游各自映射</h1>
        <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">
          同一个平台模型可以接多个上游渠道。上游不支持的参数设为 omit，字段名不同就改映射，枚举值不同就用 map。
        </p>
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <GlassCard className="p-5">
          <div className="mb-4 flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700">
              <GitBranch className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="break-words font-black text-slate-950">{adminPlatformModel.upstreamModelId}</p>
              <p className="mt-1 text-sm font-semibold leading-6 text-slate-500">
                当前只启用一条主渠道，后续可新增备用渠道并设置权重、限流和失败重试。
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
            <div className="hidden grid-cols-[1fr_1fr_0.8fr_1fr] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
              <span>平台参数</span>
              <span>上游参数</span>
              <span>转换</span>
              <span>默认值</span>
            </div>
            {adminParameters.map((parameter) => (
              <div key={parameter.key} className="grid gap-2 border-t border-slate-100 px-4 py-3 md:grid-cols-[1fr_1fr_0.8fr_1fr] md:items-center">
                <span className="font-mono text-sm font-black text-slate-900">{parameter.key}</span>
                <input className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100" defaultValue={parameter.upstream} />
                <select className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-black text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100" defaultValue={parameter.transform}>
                  <option value="direct">direct</option>
                  <option value="map">map</option>
                  <option value="default">default</option>
                  <option value="omit">omit</option>
                  <option value="template">template</option>
                </select>
                <input className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-bold text-slate-700 outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100" defaultValue={parameter.defaultValue} />
              </div>
            ))}
          </div>

          <button className="mt-4 inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-teal-700" type="button">
            <Save className="h-4 w-4" />
            保存映射草稿
          </button>
        </GlassCard>

        <GlassCard className="p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <ShieldCheck className="h-4 w-4" />
            </span>
            <div>
              <p className="text-lg font-black text-slate-950">当前渠道</p>
              <p className="text-sm font-semibold text-slate-500">用于排查前台模型调用链路。</p>
            </div>
          </div>

          <div className="mt-4 grid gap-3">
            <Info label="供应商" value={adminProvider.name} />
            <Info label="平台模型" value={adminPlatformModel.id} />
            <Info label="上游模型" value={adminPlatformModel.upstreamModelId} />
            <Info label="请求地址" value={adminPlatformModel.endpointPath} />
            <Info label="轮询地址" value={adminPlatformModel.pollPath} />
          </div>
        </GlassCard>
      </div>
    </div>
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
