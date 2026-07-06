import { AnimatePresence, motion } from "framer-motion";
import { Menu, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { type CreativeProject, listRemoteProjects } from "../../apiClient";
import { capabilityTabs, creativeModels } from "../../appData";
import type { CapabilityCategory, CreativeModel } from "../../types";
import { cn } from "../../lib";
import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { ResultPanel } from "./ResultPanel";
import { PromptComposer } from "./PromptComposer";

export function WorkspacePage({ templatePrompt }: { templatePrompt: string }) {
  const [category, setCategory] = useState<CapabilityCategory>("all");
  const [query, setQuery] = useState("");
  const [selectedModelId, setSelectedModelId] = useState(creativeModels[0].id);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [generatedPrompt, setGeneratedPrompt] = useState("");
  const [projects, setProjects] = useState<CreativeProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(() =>
    typeof window === "undefined" ? "" : window.localStorage.getItem("tikpan_selected_project_id") ?? "",
  );

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      try {
        const remoteProjects = await listRemoteProjects(50);
        if (cancelled) return;
        setProjects(remoteProjects);
        setSelectedProjectId((current) => {
          if (current && remoteProjects.some((project) => project.id === current)) return current;
          const firstProjectId = remoteProjects[0]?.id ?? "";
          if (typeof window !== "undefined") {
            if (firstProjectId) window.localStorage.setItem("tikpan_selected_project_id", firstProjectId);
            else window.localStorage.removeItem("tikpan_selected_project_id");
          }
          return firstProjectId;
        });
      } catch {
        if (!cancelled) setProjects([]);
      }
    }

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredModels = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return creativeModels.filter((model) => {
      const categoryKeys = model.categoryKeys?.length ? model.categoryKeys : [model.category];
      const matchesCategory = category === "all" || categoryKeys.includes(category);
      const matchesQuery =
        !normalizedQuery ||
        [model.name, model.slug, model.group, model.description, ...model.bestFor, ...model.tags, ...(model.aliases ?? [])]
          .filter(Boolean)
          .some((item) => String(item).toLowerCase().includes(normalizedQuery));
      return matchesCategory && matchesQuery;
    });
  }, [category, query]);

  const selectedModel = creativeModels.find((model) => model.id === selectedModelId) ?? creativeModels[0];

  const selectModel = (model: CreativeModel) => {
    setSelectedModelId(model.id);
    setMobileSidebarOpen(false);
  };

  const selectProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    if (typeof window !== "undefined") {
      if (projectId) window.localStorage.setItem("tikpan_selected_project_id", projectId);
      else window.localStorage.removeItem("tikpan_selected_project_id");
    }
  };

  const changeCategory = (nextCategory: CapabilityCategory) => {
    setCategory(nextCategory);
    const nextModel = creativeModels.find((model) => {
      const categoryKeys = model.categoryKeys?.length ? model.categoryKeys : [model.category];
      return nextCategory === "all" || categoryKeys.includes(nextCategory);
    });
    if (nextModel) setSelectedModelId(nextModel.id);
  };

  return (
    <div className="aurora-surface relative min-h-[calc(100vh-64px)] overflow-hidden">
      <div className="ambient-glow-cyan -right-28 top-10 hidden h-96 w-96 md:block" />
      <div className="ambient-glow-blue -left-32 top-60 hidden h-80 w-80 lg:block" />
      <div className="relative z-10 mx-auto flex max-w-[1540px] gap-0 px-0 lg:px-0">
        <aside className="hidden w-[286px] shrink-0 border-r border-[#ded5f6] bg-[#f2edfb]/86 lg:block">
          <WorkspaceSidebar
            category={category}
            query={query}
            selectedModelId={selectedModel.id}
            tabs={capabilityTabs}
            models={filteredModels}
            onCategoryChange={changeCategory}
            onModelSelect={selectModel}
            onQueryChange={setQuery}
          />
        </aside>

        <div className="min-w-0 flex-1 px-4 py-4 sm:px-6 lg:py-6">
          <div className="mb-3 flex items-center justify-between gap-3 lg:hidden">
            <button
              className="inline-flex h-10 items-center gap-2 rounded-full bg-[#4b16d1] px-4 text-sm font-bold text-white shadow-sm"
              type="button"
              onClick={() => setMobileSidebarOpen(true)}
            >
              <Menu className="h-4 w-4" />
              选择能力
            </button>
            <span className="truncate text-sm font-black text-slate-700">{selectedModel.name}</span>
          </div>

          <section className="flex min-h-[calc(100vh-112px)] flex-col gap-4 pb-4 md:pb-6">
            <ResultPanel generatedPrompt={generatedPrompt} model={selectedModel} />
            <PromptComposer
              initialPrompt={templatePrompt}
              model={selectedModel}
              projects={projects}
              selectedProjectId={selectedProjectId}
              onGenerate={setGeneratedPrompt}
              onProjectChange={selectProject}
            />
          </section>
        </div>
      </div>

      <AnimatePresence>
        {mobileSidebarOpen && (
          <motion.div
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-50 bg-slate-950/30 backdrop-blur-sm lg:hidden"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
          >
            <motion.aside
              animate={{ x: 0 }}
              className="h-full w-[86vw] max-w-sm bg-[#f8faf7] p-3 shadow-2xl"
              exit={{ x: "-100%" }}
              initial={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 34 }}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="inline-flex items-center gap-2 text-sm font-black text-slate-950">
                  <Sparkles className="h-4 w-4 text-[#6d32d9]" />
                  创作能力
                </div>
                <button
                  aria-label="关闭"
                  className="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
                  type="button"
                  onClick={() => setMobileSidebarOpen(false)}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <WorkspaceSidebar
                category={category}
                query={query}
                selectedModelId={selectedModel.id}
                tabs={capabilityTabs}
                models={filteredModels}
                onCategoryChange={changeCategory}
                onModelSelect={selectModel}
                onQueryChange={setQuery}
              />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
