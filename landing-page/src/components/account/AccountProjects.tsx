import { ArrowRight, FolderKanban, Image, Plus, Search, Video } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  type CreativeProject,
  type CreativeProjectInput,
  createRemoteProjectAsset,
  getRemoteProject,
  listRemoteProjects,
  saveRemoteProject,
} from "../../apiClient";
import type { AppRoute } from "../../types";
import { cn, formatTokens } from "../../lib";
import { GlassCard } from "../GlassCard";

const fallbackProjects: CreativeProject[] = [
  {
    id: "local_campaign",
    user_id: "demo_user",
    name: "New product visual campaign",
    type: "image_campaign",
    status: "active",
    description: "Manage hero images, feature graphics, social covers, and storyboard prompts in one project.",
    cover_url: null,
    tags: ["commerce", "image", "social"],
    settings: { routeMode: "quality" },
    stats: {
      tasks_total: 0,
      tasks_completed: 0,
      tasks_failed: 0,
      tasks_active: 0,
      assets_total: 0,
      token_spend: 0,
    },
    tasks: [],
    assets: [],
    created_at: "2026-07-04T09:30:00.000Z",
    updated_at: "2026-07-05T16:20:00.000Z",
    archived_at: null,
  },
];

const projectTypeLabels: Record<CreativeProject["type"], string> = {
  general: "General project",
  image_campaign: "Image campaign",
  video_storyboard: "Video storyboard",
  audio_album: "Audio album",
  agent_workspace: "Agent workspace",
};

type AccountProjectsProps = {
  onNavigate: (route: AppRoute) => void;
};

export function AccountProjects({ onNavigate }: AccountProjectsProps) {
  const [projects, setProjects] = useState<CreativeProject[]>(fallbackProjects);
  const [selectedProjectId, setSelectedProjectId] = useState(fallbackProjects[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      try {
        setStatus("loading");
        const remoteProjects = await listRemoteProjects(50);
        if (cancelled) return;
        const nextProjects = remoteProjects.length > 0 ? remoteProjects : fallbackProjects;
        setProjects(nextProjects);
        setSelectedProjectId((current) => current || nextProjects[0]?.id || "");
        setStatus("idle");
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setProjects(fallbackProjects);
        setSelectedProjectId(fallbackProjects[0]?.id ?? "");
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "Project API is unavailable. Showing a local example.");
      }
    }

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId || selectedProjectId.startsWith("local_")) return;

    let cancelled = false;

    async function loadProjectDetail() {
      try {
        const project = await getRemoteProject(selectedProjectId);
        if (cancelled) return;
        setProjects((current) => current.map((item) => (item.id === project.id ? project : item)));
        setMessage("");
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Project detail refresh failed.");
      }
    }

    void loadProjectDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return projects;
    return projects.filter((project) =>
      [project.name, project.description, project.type, ...(project.tags ?? [])]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery),
    );
  }, [projects, query]);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? visibleProjects[0] ?? projects[0];

  async function createProject() {
    const name = newProjectName.trim();
    if (!name) return;

    const input: CreativeProjectInput = {
      name,
      type: "image_campaign",
      status: "active",
      description: "Start generation tasks from this project and keep assets grouped by campaign.",
      tags: ["campaign"],
    };

    try {
      setStatus("saving");
      const project = await saveRemoteProject(input);
      setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      setSelectedProjectId(project.id);
      setNewProjectName("");
      setStatus("idle");
      setMessage("");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Project creation failed.");
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(320px,380px)_1fr]">
      <GlassCard className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-black text-teal-700">Project space</p>
            <h1 className="mt-2 text-2xl font-black tracking-normal text-slate-950">Creative projects</h1>
            <p className="mt-2 text-sm font-semibold text-slate-500">Group tasks and assets by campaign, storyboard, or content package.</p>
          </div>
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
            <FolderKanban className="h-5 w-5" />
          </span>
        </div>

        <label className="relative mt-5 block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            className="h-11 w-full rounded-full border border-slate-200 bg-white/80 pl-9 pr-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="Search projects"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <div className="mt-4 flex gap-2">
          <input
            className="h-11 min-w-0 flex-1 rounded-full border border-slate-200 bg-white/80 px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="New project name"
            value={newProjectName}
            onChange={(event) => setNewProjectName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void createProject();
            }}
          />
          <button
            aria-label="Create project"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-slate-950 text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={status === "saving" || !newProjectName.trim()}
            type="button"
            onClick={() => void createProject()}
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {message && <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{message}</p>}

        <div className="mt-5 grid gap-2">
          {visibleProjects.map((project) => (
            <button
              key={project.id}
              className={cn(
                "rounded-2xl border p-4 text-left transition",
                selectedProject?.id === project.id
                  ? "border-teal-300 bg-teal-50/80 shadow-sm"
                  : "border-slate-200 bg-white/80 hover:border-slate-300",
              )}
              type="button"
              onClick={() => setSelectedProjectId(project.id)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black text-slate-950">{project.name}</p>
                  <p className="mt-1 text-xs font-bold text-slate-500">{projectTypeLabels[project.type]}</p>
                </div>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-black text-slate-500">{project.status}</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <ProjectMiniMetric label="Tasks" value={project.stats.tasks_total} />
                <ProjectMiniMetric label="Assets" value={project.stats.assets_total} />
                <ProjectMiniMetric label="Tokens" value={project.stats.token_spend} />
              </div>
            </button>
          ))}
        </div>
      </GlassCard>

      <GlassCard className="min-w-0 p-5">
        {selectedProject ? (
          <ProjectDetail
            project={selectedProject}
            onNavigate={onNavigate}
            onProjectChange={(project) => {
              setProjects((current) => current.map((item) => (item.id === project.id ? project : item)));
            }}
          />
        ) : (
          <div className="grid min-h-[360px] place-items-center text-center">
            <div>
              <FolderKanban className="mx-auto h-10 w-10 text-slate-300" />
              <p className="mt-3 text-sm font-black text-slate-500">No projects yet</p>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function ProjectDetail({
  project,
  onNavigate,
  onProjectChange,
}: {
  project: CreativeProject;
  onNavigate: (route: AppRoute) => void;
  onProjectChange: (project: CreativeProject) => void;
}) {
  const latestTasks = project.tasks ?? [];
  const latestAssets = project.assets ?? [];
  const [assetForm, setAssetForm] = useState({
    title: "",
    sourceUrl: "",
    mimeType: "image/png",
    tags: "",
    note: "",
  });
  const [assetStatus, setAssetStatus] = useState<"idle" | "saving" | "error">("idle");
  const [assetMessage, setAssetMessage] = useState("");

  const continueInProject = () => {
    if (typeof window !== "undefined" && !project.id.startsWith("local_")) {
      window.localStorage.setItem("tikpan_selected_project_id", project.id);
    }
    onNavigate("workspace");
  };

  async function addManualAsset() {
    if (project.id.startsWith("local_") || !assetForm.title.trim() || !assetForm.sourceUrl.trim()) return;

    try {
      setAssetStatus("saving");
      await createRemoteProjectAsset(project.id, {
        title: assetForm.title.trim(),
        source_url: assetForm.sourceUrl.trim(),
        mime_type: assetForm.mimeType.trim(),
        tags: assetForm.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        note: assetForm.note.trim(),
      });
      const refreshedProject = await getRemoteProject(project.id);
      onProjectChange(refreshedProject);
      setAssetForm({ title: "", sourceUrl: "", mimeType: "image/png", tags: "", note: "" });
      setAssetStatus("idle");
      setAssetMessage("");
    } catch (error) {
      setAssetStatus("error");
      setAssetMessage(error instanceof Error ? error.message : "Asset import failed.");
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-black text-teal-700">{projectTypeLabels[project.type]}</p>
          <h2 className="mt-2 text-3xl font-black tracking-normal text-slate-950">{project.name}</h2>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-500">{project.description || "No description yet."}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(project.tags ?? []).map((tag) => (
              <span key={tag} className="rounded-full bg-white px-3 py-1 text-xs font-black text-slate-500 shadow-sm">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <button
          className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-full bg-slate-950 px-5 text-sm font-black text-white transition hover:bg-teal-600"
          type="button"
          onClick={continueInProject}
        >
          Continue creating
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white/80 p-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-black text-slate-950">Add asset URL</h3>
          <Plus className="h-4 w-4 text-slate-400" />
        </div>
        <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(120px,1fr)_minmax(180px,2fr)_150px]">
          <input
            className="h-11 min-w-0 rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="Title"
            value={assetForm.title}
            onChange={(event) => setAssetForm((current) => ({ ...current, title: event.target.value }))}
          />
          <input
            className="h-11 min-w-0 rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="https://..."
            value={assetForm.sourceUrl}
            onChange={(event) => setAssetForm((current) => ({ ...current, sourceUrl: event.target.value }))}
          />
          <select
            className="h-11 min-w-0 rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            value={assetForm.mimeType}
            onChange={(event) => setAssetForm((current) => ({ ...current, mimeType: event.target.value }))}
          >
            <option value="image/png">image/png</option>
            <option value="image/jpeg">image/jpeg</option>
            <option value="image/webp">image/webp</option>
            <option value="video/mp4">video/mp4</option>
            <option value="audio/mpeg">audio/mpeg</option>
            <option value="text/plain">text/plain</option>
          </select>
        </div>
        <div className="mt-2 grid gap-2 lg:grid-cols-[1fr_1fr_auto]">
          <input
            className="h-11 min-w-0 rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="Tags, comma separated"
            value={assetForm.tags}
            onChange={(event) => setAssetForm((current) => ({ ...current, tags: event.target.value }))}
          />
          <input
            className="h-11 min-w-0 rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 outline-none focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            placeholder="Note"
            value={assetForm.note}
            onChange={(event) => setAssetForm((current) => ({ ...current, note: event.target.value }))}
            onKeyDown={(event) => {
              if (event.key === "Enter") void addManualAsset();
            }}
          />
          <button
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-teal-600 px-5 text-sm font-black text-white transition hover:bg-slate-950 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={assetStatus === "saving" || project.id.startsWith("local_") || !assetForm.title.trim() || !assetForm.sourceUrl.trim()}
            type="button"
            onClick={() => void addManualAsset()}
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        </div>
        {assetMessage && <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{assetMessage}</p>}
      </section>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <ProjectMetric label="Total tasks" value={String(project.stats.tasks_total)} />
        <ProjectMetric label="Active" value={String(project.stats.tasks_active)} />
        <ProjectMetric label="Completed" value={String(project.stats.tasks_completed)} />
        <ProjectMetric label="Assets" value={String(project.stats.assets_total)} />
        <ProjectMetric label="Spend" value={formatTokens(project.stats.token_spend)} />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white/80 p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-black text-slate-950">Project tasks</h3>
            <Video className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-3 grid gap-2">
            {latestTasks.length > 0 ? (
              latestTasks.slice(0, 5).map((task) => (
                <div key={task.task_id} className="rounded-xl bg-slate-50 px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-black text-slate-800">{task.input?.prompt ?? task.input?.message ?? task.task_id}</p>
                    <span className="rounded-full bg-white px-2.5 py-1 text-xs font-black text-slate-500">{task.status}</span>
                  </div>
                  <p className="mt-1 text-xs font-bold text-slate-400">{task.model}</p>
                </div>
              ))
            ) : (
              <p className="rounded-xl bg-slate-50 px-3 py-6 text-center text-sm font-bold text-slate-400">No project tasks yet</p>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white/80 p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-black text-slate-950">Project assets</h3>
            <Image className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-3 grid gap-2">
            {latestAssets.length > 0 ? (
              latestAssets.slice(0, 4).map((asset) => (
                <div key={asset.id} className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
                  <div className="h-12 w-12 shrink-0 rounded-xl bg-gradient-to-br from-teal-100 to-violet-100" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-slate-800">{asset.title || asset.prompt || asset.task_id}</p>
                    <p className="mt-1 text-xs font-bold text-slate-400">{asset.model_name}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="rounded-xl bg-slate-50 px-3 py-6 text-center text-sm font-bold text-slate-400">No project assets yet</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function ProjectMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 p-4">
      <p className="text-xs font-black text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-black text-slate-950">{value}</p>
    </div>
  );
}

function ProjectMiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-xl bg-white/76 px-2 py-2">
      <span className="block text-sm font-black text-slate-900">{value}</span>
      <span className="block text-[11px] font-bold text-slate-400">{label}</span>
    </span>
  );
}
