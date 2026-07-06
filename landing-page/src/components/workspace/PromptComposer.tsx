import { Boxes, FolderHeart, ImagePlus, Loader2, SendHorizontal, SlidersHorizontal, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createRemoteTask, getRemoteTask, type CreativeProject } from "../../apiClient";
import type { OrchestratedTask, StudioInput } from "../../orchestrator";
import type { Modality, PlatformModel } from "../../productData";
import type { CreativeModel, ModelParameter } from "../../types";
import { cn, formatTokens } from "../../lib";

type ParamValue = string | number | boolean;

const TASK_POLL_INTERVAL_MS = 2500;
const MAX_TASK_POLLS = 24;

function defaultValuesFor(model: CreativeModel) {
  return model.parameters.reduce<Record<string, ParamValue>>((acc, parameter) => {
    if (parameter.defaultValue !== undefined) {
      acc[parameter.key] = parameter.defaultValue;
      return acc;
    }
    if (parameter.type === "switch") acc[parameter.key] = false;
    if (parameter.type === "number" || parameter.type === "slider") acc[parameter.key] = parameter.min ?? 0;
    if ((parameter.type === "select" || parameter.type === "segmented") && parameter.options?.[0]) {
      acc[parameter.key] = parameter.options[0].value;
    }
    return acc;
  }, {});
}

export function PromptComposer({
  initialPrompt,
  model,
  onGenerate,
  onProjectChange,
  projects,
  selectedProjectId,
}: {
  initialPrompt: string;
  model: CreativeModel;
  onGenerate: (prompt: string) => void;
  onProjectChange: (projectId: string) => void;
  projects: CreativeProject[];
  selectedProjectId: string;
}) {
  const [prompt, setPrompt] = useState("");
  const [paramValues, setParamValues] = useState<Record<string, ParamValue>>(() => defaultValuesFor(model));
  const [smartSchedule, setSmartSchedule] = useState(true);
  const [showParameters, setShowParameters] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [activeTask, setActiveTask] = useState<OrchestratedTask | null>(null);
  const pollCountRef = useRef(0);

  useEffect(() => {
    if (initialPrompt) setPrompt(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
    setParamValues(defaultValuesFor(model));
    setPrompt("");
    setStatusMessage("");
    setActiveTask(null);
    pollCountRef.current = 0;
  }, [model.id]);

  useEffect(() => {
    if (!activeTask || activeTask.lifecycle?.isTerminal) return;

    if (pollCountRef.current >= MAX_TASK_POLLS) {
      setStatusMessage(`Task ${activeTask.taskId} is still running. Check Library or Project assets for the final result.`);
      return;
    }

    let cancelled = false;
    const pollTimer = window.setTimeout(async () => {
      try {
        const nextTask = await getRemoteTask({
          taskId: activeTask.taskId,
          model: platformModelForCreativeModel(model),
          routeMode: activeTask.routeMode,
          previousTask: activeTask,
        });
        if (cancelled) return;
        pollCountRef.current += 1;
        setActiveTask(nextTask);
        setStatusMessage(formatTaskStatus(nextTask));
      } catch (error) {
        if (cancelled) return;
        setStatusMessage(error instanceof Error ? error.message : `Task ${activeTask.taskId} status check failed.`);
      }
    }, TASK_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(pollTimer);
    };
  }, [activeTask, model]);

  const updateParam = (key: string, value: ParamValue) => {
    setParamValues((current) => ({ ...current, [key]: value }));
  };

  const handleGenerate = async () => {
    const text = prompt.trim() || "A clean premium product visual that highlights material quality and core selling points.";
    const visibleParams = model.parameters
      .filter((parameter) => parameter.key !== "prompt")
      .filter((parameter) => paramValues[parameter.key] !== undefined && paramValues[parameter.key] !== "")
      .map((parameter) => `${parameter.label} ${String(paramValues[parameter.key])}`)
      .join(", ");

    setGenerating(true);
    setStatusMessage("");
    setActiveTask(null);
    pollCountRef.current = 0;

    try {
      const platformModel = platformModelForCreativeModel(model);
      const task = await createRemoteTask({
        model: platformModel,
        input: buildStudioInput(model, text, paramValues),
        routeMode: "quality",
        projectId: selectedProjectId || undefined,
      });
      const projectName = projects.find((project) => project.id === selectedProjectId)?.name;
      setActiveTask(task);
      setStatusMessage(formatTaskStatus(task, projectName));
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Remote task failed. Showing local preview.");
    } finally {
      setGenerating(false);
      onGenerate(`${text}${visibleParams ? `, ${visibleParams}` : ""}`);
    }
  };

  return (
    <div className="breathing-shell sticky bottom-3 z-20 mx-auto w-full max-w-6xl rounded-3xl border border-[#cdb8ff] bg-white/80 p-3 shadow-[0_22px_80px_rgba(121,86,220,0.16)] backdrop-blur-2xl md:bottom-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 px-2">
        <span className="rounded-full border border-[#ded5f6] bg-white px-3 py-1.5 text-xs font-black text-slate-700 shadow-sm">{model.name}</span>
        <span className="rounded-full border border-[#ded5f6] bg-white px-3 py-1.5 text-xs font-black text-slate-600">
          {model.parameters.length} params · est. {formatTokens(model.cost)}
        </span>
        <label className="inline-flex max-w-full items-center gap-2 rounded-full border border-[#ded5f6] bg-white px-3 py-1.5 text-xs font-black text-slate-600 shadow-sm">
          <FolderHeart className="h-3.5 w-3.5 text-teal-600" />
          <select
            className="max-w-[220px] bg-transparent text-xs font-black text-slate-700 outline-none"
            value={selectedProjectId}
            onChange={(event) => onProjectChange(event.target.value)}
          >
            <option value="">No project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="rounded-2xl border border-[#eee7ff] bg-white/76 p-3">
        <textarea
          className="min-h-16 w-full resize-none border-0 bg-transparent p-1 text-base font-semibold leading-7 text-slate-800 outline-none placeholder:text-slate-400"
          placeholder="Describe what you want to create or paste source material..."
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />

        <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
          <div className="grid gap-2">
            <div className="flex flex-wrap gap-2">
              <ComposerAction icon={Zap} label="Smart route" active={smartSchedule} onClick={() => setSmartSchedule((current) => !current)} />
              <ComposerAction icon={ImagePlus} label="Attach 0/10" />
              <ComposerAction icon={Boxes} label="Save kit" />
              <ComposerAction icon={FolderHeart} label="Project context" active={Boolean(selectedProjectId)} />
              <ComposerAction icon={SlidersHorizontal} label="Params" active={showParameters} onClick={() => setShowParameters((current) => !current)} />
            </div>
            {showParameters && (
              <div className="grid max-h-[26vh] gap-2 overflow-y-auto pr-1 sm:grid-cols-2 md:max-h-[34vh] xl:grid-cols-4">
                {model.parameters
                  .filter((parameter) => parameter.key !== "prompt")
                  .map((parameter) => (
                    <ParameterControl key={parameter.key} parameter={parameter} value={paramValues[parameter.key]} onChange={(value) => updateParam(parameter.key, value)} />
                  ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 lg:items-end">
            <div className="flex flex-col gap-1 sm:items-end">
              <p className="text-xs font-semibold text-slate-500">Estimated spend {formatTokens(model.cost)}. Failed tasks release frozen Tokens.</p>
              {statusMessage && <p className="max-w-xs text-right text-xs font-bold text-teal-700">{statusMessage}</p>}
              <button
                className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-white text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:text-[#6d32d9] disabled:cursor-not-allowed disabled:opacity-70"
                type="button"
                disabled={generating}
                onClick={() => void handleGenerate()}
              >
                {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizontal className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTaskStatus(task: OrchestratedTask, projectName?: string) {
  const apiStatus = task.lifecycle?.apiStatus ?? (task.status === "blocked" ? "failed" : "queued");
  const progress =
    typeof task.lifecycle?.progress === "number" && task.lifecycle.progress > 0 ? ` ${Math.round(task.lifecycle.progress)}%` : "";
  const currentStep = task.lifecycle?.currentStep || apiStatus;
  const location = projectName ? ` in ${projectName}` : "";

  if (task.lifecycle?.isTerminal) {
    if (apiStatus === "completed" || apiStatus === "succeeded") {
      const outputs = task.lifecycle.outputUrls?.length ?? 0;
      return outputs > 0 ? `Task ${task.taskId} completed with ${outputs} output${outputs === 1 ? "" : "s"}.` : `Task ${task.taskId} completed.`;
    }
    return `Task ${task.taskId} ${apiStatus}: ${task.userVisible.message}`;
  }

  return `Task ${task.taskId}${location}: ${currentStep}${progress}.`;
}

function buildStudioInput(model: CreativeModel, prompt: string, paramValues: Record<string, ParamValue>): StudioInput {
  const input: StudioInput = { ...paramValues, prompt };
  if (model.platformModelId.includes(".chat.") || model.category === "chat") {
    input.message = prompt;
  }
  return input;
}

function platformModelForCreativeModel(model: CreativeModel): PlatformModel {
  const modality: Modality =
    model.category === "chat" ? "chat" : model.category === "video" ? "video" : model.category === "audio" ? "audio" : "image";

  return {
    id: model.platformModelId,
    name: model.name,
    shortName: model.name,
    modality,
    icon: model.icon,
    tier: "Pro",
    tagline: model.description,
    description: model.description,
    useCases: model.bestFor,
    price: String(model.cost),
    eta: "Async task",
    stability: model.health,
    recommended: true,
    schema: model.parameters.map((parameter) => ({
      key: parameter.key,
      label: parameter.label,
      type: parameter.type === "number" ? "slider" : parameter.type,
      required: parameter.required,
      advanced: parameter.advanced,
      placeholder: parameter.helper,
      defaultValue: parameter.defaultValue,
      min: parameter.min,
      max: parameter.max,
      step: parameter.step,
      options: parameter.options?.map((option) => ({ label: option.label, value: String(option.value) })),
    })),
  };
}

function ComposerAction({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active?: boolean;
  icon: typeof Zap;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-full px-3 text-xs font-black transition",
        active ? "bg-[#eef3ff] text-[#1261a6] ring-1 ring-[#d7dcff]" : "bg-white text-slate-600 ring-1 ring-[#ded5f6] hover:text-[#6d32d9]",
      )}
      type="button"
      onClick={onClick}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function ParameterControl({
  parameter,
  value,
  onChange,
}: {
  parameter: ModelParameter;
  value: ParamValue | undefined;
  onChange: (value: ParamValue) => void;
}) {
  const label = (
    <div className="flex items-center justify-between gap-2">
      <span className="truncate text-xs font-black text-slate-500">{parameter.label}</span>
      {parameter.advanced && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-black text-slate-400">Advanced</span>}
    </div>
  );

  const helper = parameter.helper ? (
    <p className="truncate text-[11px] font-semibold text-slate-400" title={parameter.helper}>
      {parameter.helper}
    </p>
  ) : null;

  if (parameter.type === "switch") {
    return (
      <div className="grid gap-2 rounded-xl bg-slate-50/80 p-2.5">
        {label}
        <button
          className={cn(
            "h-9 rounded-lg px-3 text-xs font-black transition",
            value ? "bg-[#4b16d1] text-white" : "bg-white text-slate-500 ring-1 ring-[#ded5f6] hover:text-[#6d32d9]",
          )}
          type="button"
          onClick={() => onChange(!value)}
        >
          {value ? "On" : "Off"}
        </button>
        {helper}
      </div>
    );
  }

  if (parameter.type === "slider" || parameter.type === "number") {
    const numericValue = Number(value ?? parameter.defaultValue ?? parameter.min ?? 0);
    return (
      <div className="grid gap-2 rounded-xl bg-slate-50/80 p-2.5">
        {label}
        <div className="flex items-center gap-2">
          <input
            className="h-9 w-24 rounded-lg border border-[#ded5f6] bg-white px-3 text-xs font-black text-slate-700 outline-none focus:border-[#b899ff] focus:ring-4 focus:ring-[#eee6ff]"
            max={parameter.max}
            min={parameter.min}
            step={parameter.step ?? 1}
            type="number"
            value={numericValue}
            onChange={(event) => onChange(Number(event.target.value))}
          />
          {parameter.type === "slider" && (
            <input
              className="h-8 min-w-0 flex-1 accent-[#6d32d9]"
              max={parameter.max}
              min={parameter.min}
              step={parameter.step ?? 1}
              type="range"
              value={numericValue}
              onChange={(event) => onChange(Number(event.target.value))}
            />
          )}
        </div>
        {helper}
      </div>
    );
  }

  if (parameter.type === "select") {
    return (
      <div className="grid gap-2 rounded-xl bg-slate-50/80 p-2.5">
        {label}
        <select
          className="h-9 w-full rounded-lg border border-[#ded5f6] bg-white px-3 text-xs font-black text-slate-700 outline-none focus:border-[#b899ff] focus:ring-4 focus:ring-[#eee6ff]"
          value={String(value ?? parameter.defaultValue ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {parameter.options?.map((option) => (
            <option key={String(option.value)} value={String(option.value)}>
              {option.label}
            </option>
          ))}
        </select>
        {helper}
      </div>
    );
  }

  if (parameter.type === "text") {
    return (
      <label className="grid gap-2 rounded-xl bg-slate-50/80 p-2.5">
        {label}
        <input
          className="h-9 rounded-lg border border-[#ded5f6] bg-white px-3 text-xs font-black text-slate-700 outline-none focus:border-[#b899ff] focus:ring-4 focus:ring-[#eee6ff]"
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    );
  }

  return (
    <div className="grid gap-2 rounded-xl bg-slate-50/80 p-2.5">
      {label}
      <div className="flex flex-wrap gap-1.5">
        {parameter.options?.map((option) => (
          <button
            key={String(option.value)}
            className={cn(
              "h-8 rounded-lg px-3 text-xs font-black transition",
              String(option.value) === String(value ?? parameter.defaultValue ?? "") ? "bg-[#4b16d1] text-white" : "bg-white text-slate-500 ring-1 ring-[#ded5f6] hover:text-[#6d32d9]",
            )}
            type="button"
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {helper}
    </div>
  );
}
