import { Download, Heart, Search, WandSparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { libraryAssets } from "../../appData";
import type { AppRoute } from "../../types";
import { cn } from "../../lib";
import { GlassCard } from "../GlassCard";

const filters = ["全部", "图片", "视频"];

export function AccountLibrary({ onNavigate }: { onNavigate: (route: AppRoute) => void }) {
  const [filter, setFilter] = useState("全部");
  const [query, setQuery] = useState("");

  const visibleAssets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return libraryAssets.filter((asset) => {
      const matchesFilter = filter === "全部" || asset.type === filter;
      const matchesQuery = !normalizedQuery || [asset.title, asset.model, asset.type].some((item) => item.toLowerCase().includes(normalizedQuery));
      return matchesFilter && matchesQuery;
    });
  }, [filter, query]);

  return (
    <GlassCard className="p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-black text-teal-700">我的作品</p>
          <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">统一归档</h1>
          <p className="mt-2 text-sm font-semibold text-slate-500">图片和视频成品都在这里。</p>
        </div>
        <label className="relative w-full lg:w-80">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            className="h-11 w-full rounded-full border border-slate-200 bg-white/80 pl-9 pr-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="搜索作品"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {filters.map((item) => (
          <button
            key={item}
            className={cn("rounded-full px-4 py-2 text-sm font-black transition", filter === item ? "bg-slate-950 text-white" : "bg-white/80 text-slate-500 hover:bg-slate-100")}
            type="button"
            onClick={() => setFilter(item)}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {visibleAssets.map((asset) => (
          <article key={asset.id} className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white/82 shadow-sm">
            <div className="result-tile h-36" />
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black text-slate-950">{asset.title}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-500">{asset.createdAt} · {asset.model}</p>
                </div>
                {asset.favorite && <Heart className="h-4 w-4 fill-rose-500 text-rose-500" />}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button className="inline-flex items-center gap-1.5 rounded-full bg-slate-950 px-3 py-2 text-xs font-black text-white" type="button" onClick={() => onNavigate("workspace")}>
                  <WandSparkles className="h-3.5 w-3.5" />
                  继续创作
                </button>
                <button className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-2 text-xs font-black text-slate-600" type="button">
                  <Download className="h-3.5 w-3.5" />
                  下载
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </GlassCard>
  );
}
