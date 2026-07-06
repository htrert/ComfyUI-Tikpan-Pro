import { Bell, LogOut, Mail, UserRound } from "lucide-react";
import type { UserProfile } from "../../types";
import { GlassCard } from "../GlassCard";

export function AccountSettings({ user }: { user: UserProfile }) {
  return (
    <GlassCard className="p-5">
      <p className="text-sm font-black text-teal-700">账号设置</p>
      <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">个人资料</h1>
      <p className="mt-2 text-sm font-semibold text-slate-500">当前为已登录状态。</p>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <label className="grid gap-2">
          <span className="flex items-center gap-2 text-xs font-black text-slate-500">
            <UserRound className="h-4 w-4" />
            昵称
          </span>
          <input className="h-12 rounded-xl border border-slate-200 bg-white/80 px-4 text-sm font-bold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100" defaultValue={user.name} />
        </label>
        <label className="grid gap-2">
          <span className="flex items-center gap-2 text-xs font-black text-slate-500">
            <Mail className="h-4 w-4" />
            邮箱
          </span>
          <input className="h-12 rounded-xl border border-slate-200 bg-white/80 px-4 text-sm font-bold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100" defaultValue={user.email} />
        </label>
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200/70 bg-white/78 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
              <Bell className="h-4 w-4" />
            </span>
            <div>
              <p className="font-black text-slate-950">通知设置</p>
              <p className="mt-1 text-sm font-semibold text-slate-500">任务完成、失败退回和额度变化提醒。</p>
            </div>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-sm font-black text-slate-600">
            <input defaultChecked className="accent-teal-600" type="checkbox" />
            开启
          </label>
        </div>
      </div>

      <button className="mt-5 inline-flex h-11 items-center gap-2 rounded-full bg-rose-50 px-5 text-sm font-black text-rose-700 transition hover:bg-rose-100" type="button">
        <LogOut className="h-4 w-4" />
        退出登录
      </button>
    </GlassCard>
  );
}
