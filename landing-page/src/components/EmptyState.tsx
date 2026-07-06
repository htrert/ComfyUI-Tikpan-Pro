import type { LucideIcon } from "lucide-react";
import { Sparkles } from "lucide-react";

export function EmptyState({
  icon: Icon = Sparkles,
  title,
  copy,
}: {
  icon?: LucideIcon;
  title: string;
  copy: string;
}) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/50 px-4 py-8 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-full bg-teal-50 text-teal-700">
        <Icon className="h-5 w-5" />
      </span>
      <p className="mt-4 text-sm font-black text-slate-950">{title}</p>
      <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">{copy}</p>
    </div>
  );
}
