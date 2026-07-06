import { tasks } from "../store.mjs";

export const tasksRepository = {
  list() {
    return tasks;
  },

  listByUser(userId) {
    return tasks.filter((task) => task.userId === userId);
  },

  findById(id) {
    return tasks.find((task) => task.id === id);
  },

  create(task) {
    tasks.push(task);
    return task;
  },

  save(task) {
    return task;
  },

  claimNextQueued({ workerId, lockTtlMs }) {
    const now = Date.now();
    const expiresAt = new Date(now + lockTtlMs).toISOString();
    const task = tasks
      .filter((item) => ["queued", "running", "saving_media"].includes(item.status))
      .filter((item) => !item.finishedAt)
      .filter((item) => !item.lockedUntil || new Date(item.lockedUntil).getTime() <= now || item.workerId === workerId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())[0];

    if (!task) {
      return null;
    }

    task.workerId = workerId;
    task.lockedUntil = expiresAt;
    task.lockVersion = Number(task.lockVersion ?? 0) + 1;
    return task;
  },

  releaseClaim(taskId, workerId) {
    const task = tasks.find((item) => item.id === taskId);
    if (!task || task.workerId !== workerId) {
      return null;
    }

    task.workerId = null;
    task.lockedUntil = null;
    return task;
  },
};
