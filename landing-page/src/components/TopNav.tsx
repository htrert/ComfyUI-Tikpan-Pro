import { Bell, CreditCard, Sparkles } from "lucide-react";
import type { AccountSection, AppRoute, UserProfile } from "../types";
import { cn } from "../lib";
import { TokenBadge } from "./TokenBadge";
import { UserMenu } from "./UserMenu";

type TopNavProps = {
  route: AppRoute;
  user: UserProfile;
  onNavigate: (route: AppRoute, section?: AccountSection) => void;
};

export function TopNav({ route, user, onNavigate }: TopNavProps) {
  const navItems: Array<{ route: AppRoute; label: string }> = [
    { route: "workspace", label: "创作工作台" },
    { route: "explore", label: "探索广场" },
  ];

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-[#ded5f6] bg-white/76 backdrop-blur-2xl">
      <div className="mx-auto flex h-full max-w-[1500px] items-center justify-between gap-3 px-4 sm:px-6">
        <button
          className="flex min-w-0 items-center gap-2 rounded-full px-2 py-1 text-left transition hover:bg-white/70"
          type="button"
          onClick={() => onNavigate("workspace")}
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#eee6ff] text-[#6d32d9] shadow-sm">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="hidden text-sm font-black tracking-normal text-slate-950 sm:block">Tikpan AI</span>
        </button>

        <nav className="flex shrink-0 rounded-full border border-[#ded5f6] bg-white/70 p-1 shadow-sm">
          {navItems.map((item) => (
            <button
              key={item.route}
              className={cn(
                "h-9 rounded-full px-3 text-sm font-bold transition sm:px-5",
                route === item.route ? "bg-[#eee6ff] text-[#4b16d1] shadow-sm" : "text-slate-500 hover:bg-[#f7f3ff] hover:text-[#6d32d9]",
              )}
              type="button"
              onClick={() => onNavigate(item.route)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="flex min-w-0 items-center justify-end gap-2">
          <button
            aria-label="通知"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-[#ded5f6] bg-white/75 text-slate-600 shadow-sm transition hover:border-[#b899ff] hover:text-[#6d32d9]"
            type="button"
          >
            <Bell className="h-4 w-4" />
          </button>
          <TokenBadge tokens={user.tokens} />
          <button
            className="hidden h-10 items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 text-sm font-bold text-emerald-700 shadow-sm transition hover:bg-emerald-100 md:inline-flex"
            type="button"
            onClick={() => onNavigate("account", "assets")}
          >
            <CreditCard className="h-4 w-4" />
            充值
          </button>
          <UserMenu user={user} onNavigate={onNavigate} />
        </div>
      </div>
    </header>
  );
}
