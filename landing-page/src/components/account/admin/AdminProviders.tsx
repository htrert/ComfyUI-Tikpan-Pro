import { KeyRound, Save, ServerCog } from "lucide-react";
import { useState } from "react";
import { adminPlatformModel, adminProvider } from "../../../adminData";
import { GlassCard } from "../../GlassCard";

export function AdminProviders() {
  const [baseUrl, setBaseUrl] = useState(adminProvider.baseUrl);
  const [upstreamModel, setUpstreamModel] = useState(adminPlatformModel.upstreamModelId);

  return (
    <div className="grid gap-4">
      <GlassCard className="p-5">
        <p className="text-sm font-black text-teal-700">供应商渠道</p>
        <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">上游中转配置</h1>
        <p className="mt-2 text-sm font-semibold leading-6 text-slate-500">
          先只接沧元算力；后续可以继续新增其他中转站，并给同一个平台模型配置多条渠道。
        </p>
      </GlassCard>

      <GlassCard className="p-5">
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="供应商名称" value={adminProvider.name} />
          <Field label="供应商 ID" value={adminProvider.id} />
          <EditableField label="Base URL" value={baseUrl} onChange={setBaseUrl} />
          <Field label="鉴权方式" value={adminProvider.authType} />
          <EditableField label="上游模型 ID" value={upstreamModel} onChange={setUpstreamModel} />
          <Field label="提交接口" value={adminPlatformModel.endpointPath} />
          <Field label="轮询接口" value={adminPlatformModel.pollPath} />
          <Field label="超时" value={`${adminProvider.timeoutMs} ms`} />
        </div>

        <div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50/80 p-4">
          <div className="flex items-start gap-3">
            <KeyRound className="mt-0.5 h-5 w-5 text-amber-600" />
            <div>
              <p className="text-sm font-black text-amber-900">API Key 不保存在前端</p>
              <p className="mt-1 text-sm font-semibold leading-6 text-amber-800">
                在本地或服务器环境变量里设置 <code className="font-mono">TIKPAN_PROVIDER_SECRETS</code>，格式是{" "}
                <code className="font-mono">{'{"cangyuan":"sk-你的令牌"}'}</code>。
              </p>
            </div>
          </div>
        </div>

        <button className="mt-4 inline-flex h-10 items-center gap-2 rounded-full bg-violet-700 px-4 text-sm font-black text-white" type="button">
          <Save className="h-4 w-4" />
          保存渠道草稿
        </button>
      </GlassCard>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200/70 bg-white/78 p-3">
      <p className="text-xs font-black text-slate-400">{label}</p>
      <p className="mt-2 break-words font-mono text-sm font-black text-slate-900">{value}</p>
    </div>
  );
}

function EditableField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-black text-slate-500">{label}</span>
      <input className="h-11 rounded-xl border border-slate-200 bg-white/80 px-3 font-mono text-sm font-bold text-slate-700 outline-none focus:border-violet-300 focus:ring-4 focus:ring-violet-100" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
