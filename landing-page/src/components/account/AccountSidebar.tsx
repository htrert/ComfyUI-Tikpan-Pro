import { BookImage, FolderKanban, GitBranch, LayoutDashboard, MonitorCog, ReceiptText, ServerCog, Settings, SlidersHorizontal, WalletCards } from "lucide-react";
import type { UserProfile } from "../../types";
import type { AccountSection } from "../../types";
import { cn } from "../../lib";
import { GlassCard } from "../GlassCard";

const baseSections: Array<{ key: AccountSection; label: string; icon: typeof WalletCards }> = [
  { key: "projects", label: "Projects", icon: FolderKanban },
  { key: "assets", label: "我的资产", icon: WalletCards },
  { key: "library", label: "我的作品", icon: BookImage },
  { key: "presets", label: "创作预设", icon: SlidersHorizontal },
  { key: "orders", label: "充值订单", icon: ReceiptText },
  { key: "settings", label: "账号设置", icon: Settings },
];

const adminSections: Array<{ key: AccountSection; label: string; icon: typeof WalletCards }> = [
  { key: "admin-overview", label: "管理概览", icon: LayoutDashboard },
  { key: "admin-frontend", label: "前台配置", icon: MonitorCog },
  { key: "admin-models", label: "模型配置", icon: SlidersHorizontal },
  { key: "admin-providers", label: "供应商渠道", icon: ServerCog },
  { key: "admin-routing", label: "参数映射", icon: GitBranch },
];

export function AccountSidebar({
  activeSection,
  user,
  onActiveSectionChange,
}: {
  activeSection: AccountSection;
  user: UserProfile;
  onActiveSectionChange: (section: AccountSection) => void;
}) {
  const sections = user.role === "admin" ? [...baseSections, ...adminSections] : baseSections;

  return (
    <GlassCard className="h-fit p-3">
      <div className="px-2 py-2">
        <p className="text-lg font-black text-slate-950">账户中心</p>
        <p className="mt-1 text-sm font-semibold text-slate-500">管理资产、作品和创作偏好。</p>
      </div>
      <nav className="mt-3 grid gap-1">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <button
              key={section.key}
              className={cn(
                "flex h-11 items-center gap-3 rounded-xl px-3 text-left text-sm font-black transition",
                activeSection === section.key ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-white/80 hover:text-slate-950",
              )}
              type="button"
              onClick={() => onActiveSectionChange(section.key)}
            >
              <Icon className="h-4 w-4" />
              {section.label}
            </button>
          );
        })}
      </nav>
    </GlassCard>
  );
}
