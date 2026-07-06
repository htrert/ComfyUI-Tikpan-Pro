import { Wallet } from "lucide-react";
import { formatTokens } from "../lib";

export function TokenBadge({ tokens }: { tokens: number }) {
  return (
    <div className="hidden h-10 items-center gap-2 rounded-full border border-emerald-100 bg-white/75 px-3 text-sm font-black text-slate-800 shadow-sm sm:inline-flex">
      <span className="status-dot" />
      <Wallet className="h-4 w-4 text-emerald-600" />
      {formatTokens(tokens)}
    </div>
  );
}
