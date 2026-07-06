import { config } from "../config.mjs";
import { processClaimedTask } from "../orchestrator.mjs";
import { repositories } from "../repositories/index.mjs";

const tasksRepository = repositories.tasks;

export function createQueueWorker({
  workerId = config.worker.id,
  pollIntervalMs = config.worker.pollIntervalMs,
  lockTtlMs = config.worker.lockTtlMs,
} = {}) {
  let timer = null;
  let running = false;
  let stopped = true;
  let lastError = null;
  let tickCount = 0;
  let completedCount = 0;

  async function tick() {
    if (stopped || running) {
      return;
    }

    running = true;
    try {
      const task = await tasksRepository.claimNextQueued({ workerId, lockTtlMs });
      if (!task) {
        return;
      }

      const result = await processClaimedTask(task);
      tickCount += 1;
      if (["completed", "failed", "cancelled", "expired"].includes(result?.status)) {
        completedCount += 1;
      }

      if (tasksRepository.releaseClaim) {
        await tasksRepository.releaseClaim(task.id, workerId);
      }
    } catch (error) {
      lastError = {
        message: error?.message ?? "Queue worker failed.",
        code: error?.code ?? "WORKER_ERROR",
        at: new Date().toISOString(),
      };
    } finally {
      running = false;
    }
  }

  function start() {
    if (!stopped) {
      return;
    }

    stopped = false;
    void tick();
    timer = setInterval(() => {
      void tick();
    }, pollIntervalMs);
  }

  function stop() {
    stopped = true;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function getStatus() {
    return {
      enabled: config.worker.enabled,
      running,
      worker_id: workerId,
      poll_interval_ms: pollIntervalMs,
      lock_ttl_ms: lockTtlMs,
      tick_count: tickCount,
      completed_count: completedCount,
      last_error: lastError,
    };
  }

  return {
    start,
    stop,
    getStatus,
  };
}
