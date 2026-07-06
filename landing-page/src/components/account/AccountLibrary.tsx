import { Download, FolderKanban, Heart, Search, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { libraryAssets } from "../../appData";
import { type CreativeProject, type GenerationAsset, listRemoteAssets, listRemoteProjects } from "../../apiClient";
import type { AppRoute, LibraryAsset } from "../../types";
import { cn } from "../../lib";
import { GlassCard } from "../GlassCard";

type LibraryItem = {
  id: string;
  taskId?: string;
  title: string;
  type: string;
  createdAt: string;
  model: string;
  favorite?: boolean;
  projectId?: string | null;
  projectName?: string | null;
  prompt?: string;
  outputUrls?: string[];
};

const filters = ["All", "Image", "Video", "Audio", "Text"];

export function AccountLibrary({ onNavigate }: { onNavigate: (route: AppRoute) => void }) {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [projectId, setProjectId] = useState("");
  const [items, setItems] = useState<LibraryItem[]>(() => libraryAssets.map(mapLocalAsset));
  const [projects, setProjects] = useState<CreativeProject[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadLibrary() {
      try {
        const [remoteAssets, remoteProjects] = await Promise.all([listRemoteAssets(80), listRemoteProjects(50)]);
        if (cancelled) return;
        setItems(remoteAssets.map(mapRemoteAsset));
        setProjects(remoteProjects);
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setItems(libraryAssets.map(mapLocalAsset));
        setProjects([]);
        setMessage(error instanceof Error ? error.message : "Asset API is unavailable. Showing local examples.");
      }
    }

    void loadLibrary();
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleAssets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((asset) => {
      const matchesFilter = filter === "All" || asset.type === filter;
      const matchesProject = !projectId || asset.projectId === projectId;
      const matchesQuery =
        !normalizedQuery ||
        [asset.title, asset.model, asset.type, asset.projectName, asset.prompt]
          .filter(Boolean)
          .some((item) => String(item).toLowerCase().includes(normalizedQuery));
      return matchesFilter && matchesProject && matchesQuery;
    });
  }, [filter, items, projectId, query]);

  return (
    <GlassCard className="p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-black text-teal-700">Asset library</p>
          <h1 className="mt-2 text-3xl font-black tracking-normal text-slate-950">Unified archive</h1>
          <p className="mt-2 text-sm font-semibold text-slate-500">Generated images, videos, audio, and text results stay connected to projects.</p>
        </div>
        <div className="grid w-full gap-2 lg:w-[420px]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="h-11 w-full rounded-full border border-slate-200 bg-white/80 pl-9 pr-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              placeholder="Search assets"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="inline-flex h-11 items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 text-sm font-black text-slate-600">
            <FolderKanban className="h-4 w-4 text-teal-600" />
            <select className="min-w-0 flex-1 bg-transparent outline-none" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {message && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}

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
                  <p className="mt-1 text-xs font-semibold text-slate-500">
                    {asset.createdAt} · {asset.model}
                  </p>
                  {asset.projectName && (
                    <p className="mt-2 inline-flex max-w-full items-center gap-1 rounded-full bg-teal-50 px-2.5 py-1 text-xs font-black text-teal-700">
                      <FolderKanban className="h-3 w-3" />
                      <span className="truncate">{asset.projectName}</span>
                    </p>
                  )}
                </div>
                {asset.favorite && <Heart className="h-4 w-4 fill-rose-500 text-rose-500" />}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button className="inline-flex items-center gap-1.5 rounded-full bg-slate-950 px-3 py-2 text-xs font-black text-white" type="button" onClick={() => onNavigate("workspace")}>
                  <WandSparkles className="h-3.5 w-3.5" />
                  Continue
                </button>
                <button className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-2 text-xs font-black text-slate-600" type="button">
                  <Download className="h-3.5 w-3.5" />
                  Download
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </GlassCard>
  );
}

function mapRemoteAsset(asset: GenerationAsset): LibraryItem {
  return {
    id: asset.id,
    taskId: asset.task_id,
    title: asset.title || asset.prompt || asset.task_id,
    type: modalityLabel(asset.modality),
    createdAt: formatShortDate(asset.finished_at ?? asset.created_at),
    model: asset.model_name,
    favorite: asset.favorite,
    projectId: asset.project_id ?? null,
    projectName: asset.project_name ?? null,
    prompt: asset.prompt,
    outputUrls: asset.output_urls,
  };
}

function mapLocalAsset(asset: LibraryAsset): LibraryItem {
  return {
    id: asset.id,
    title: asset.title,
    type: asset.type.includes("视频") ? "Video" : "Image",
    createdAt: asset.createdAt,
    model: asset.model,
    favorite: asset.favorite,
  };
}

function modalityLabel(modality: GenerationAsset["modality"]) {
  if (modality === "video") return "Video";
  if (modality === "audio") return "Audio";
  if (modality === "chat") return "Text";
  return "Image";
}

function formatShortDate(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
