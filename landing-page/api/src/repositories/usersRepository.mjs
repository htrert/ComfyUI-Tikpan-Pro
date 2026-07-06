import { users } from "../store.mjs";

export const usersRepository = {
  list() {
    return users;
  },

  findById(id) {
    return users.find((user) => user.id === id) ?? null;
  },

  upsert(user) {
    const index = users.findIndex((item) => item.id === user.id);
    if (index >= 0) {
      users[index] = { ...users[index], ...user, updatedAt: new Date().toISOString() };
      return users[index];
    }

    users.push(user);
    return user;
  },
};
