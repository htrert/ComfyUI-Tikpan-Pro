import { projects } from "../store.mjs";

export const projectsRepository = {
  list({ userId, includeArchived = false, limit = 50 } = {}) {
    return projects
      .filter((project) => !userId || project.userId === userId)
      .filter((project) => includeArchived || project.status !== "archived")
      .slice()
      .sort((a, b) => new Date(b.updatedAt ?? b.createdAt).getTime() - new Date(a.updatedAt ?? a.createdAt).getTime())
      .slice(0, limit);
  },

  findById(id) {
    return projects.find((project) => project.id === id) ?? null;
  },

  create(project) {
    projects.push(project);
    return project;
  },

  save(project) {
    const index = projects.findIndex((item) => item.id === project.id);
    if (index >= 0) {
      projects[index] = project;
    }
    return project;
  },

  delete(id) {
    const index = projects.findIndex((project) => project.id === id);
    if (index < 0) {
      return false;
    }

    projects.splice(index, 1);
    return true;
  },
};
