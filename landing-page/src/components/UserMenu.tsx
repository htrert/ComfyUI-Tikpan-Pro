import { AnimatePresence, motion } from "framer-motion";
import { BookImage, LogOut, ReceiptText, Settings, Shield, SlidersHorizontal, UserRound } from "lucide-react";
import { useState } from "react";
import type { AccountSection, AppRoute, UserProfile } from "../types";

type UserMenuProps = {
  user: UserProfile;
  onNavigate: (route: AppRoute, section?: AccountSection) => void;
};

const accountItems: Array<{ label: string; section: AccountSection; icon: typeof UserRound }> = [
  { label: "账户中心", section: "assets", icon: UserRound },
  { label: "我的作品", section: "library", icon: BookImage },
  { label: "创作预设", section: "presets", icon: SlidersHorizontal },
  { label: "充值订单", section: "orders", icon: ReceiptText },
  { label: "账号设置", section: "settings", icon: Settings },
];

export function UserMenu({ user, onNavigate }: UserMenuProps) {
  const [open, setOpen] = useState(false);

  const goAccount = (section: AccountSection) => {
    setOpen(false);
    onNavigate("account", section);
  };

  return (
    <div className="relative">
      <button
        aria-label="用户菜单"
        className="grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-[#4b16d1] via-[#7c3aed] to-[#c4b5fd] text-sm font-black text-white shadow-sm ring-2 ring-white"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {user.initials}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="absolute right-0 top-12 w-64 overflow-hidden rounded-2xl border border-white/80 bg-white/95 p-2 shadow-[0_20px_60px_rgba(15,23,42,0.14)] backdrop-blur-2xl"
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.16 }}
          >
            <div className="px-3 py-3">
              <p className="text-sm font-black text-slate-950">{user.name}</p>
              <p className="mt-1 truncate text-xs font-semibold text-slate-500">{user.email}</p>
            </div>
            <div className="grid gap-1">
              {accountItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.section}
                    className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-bold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
                    type="button"
                    onClick={() => goAccount(item.section)}
                  >
                    <Icon className="h-4 w-4 text-slate-400" />
                    {item.label}
                  </button>
                );
              })}
              {user.role === "admin" && (
                <button
                  className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-bold text-slate-600 transition hover:bg-teal-50 hover:text-teal-800"
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    onNavigate("account", "admin-overview");
                  }}
                >
                  <Shield className="h-4 w-4 text-teal-600" />
                  管理配置
                </button>
              )}
              <button
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-bold text-slate-500 transition hover:bg-rose-50 hover:text-rose-700"
                type="button"
                onClick={() => setOpen(false)}
              >
                <LogOut className="h-4 w-4" />
                退出登录
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
