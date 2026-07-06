import { orders } from "../../appData";
import { formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

export function AccountOrders() {
  return (
    <GlassCard className="p-5">
      <p className="text-sm font-black text-teal-700">充值订单</p>
      <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Tokens 记录</h1>
      <p className="mt-2 text-sm font-semibold text-slate-500">这里只显示 Tokens 数量、状态和时间。</p>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/78">
        <div className="hidden grid-cols-[1.2fr_0.8fr_0.8fr_1fr] bg-slate-50 px-4 py-3 text-xs font-black text-slate-400 md:grid">
          <span>订单号</span>
          <span>充值 Tokens</span>
          <span>状态</span>
          <span>时间</span>
        </div>
        {orders.map((order) => (
          <div key={order.id} className="grid gap-2 border-t border-slate-100 px-4 py-4 text-sm md:grid-cols-[1.2fr_0.8fr_0.8fr_1fr] md:items-center">
            <span className="font-black text-slate-950">{order.id}</span>
            <span className="font-bold text-slate-700">{formatTokens(order.tokens)}</span>
            <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">{order.status}</span>
            <span className="font-semibold text-slate-500">{order.time}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
