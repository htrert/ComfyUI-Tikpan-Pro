import { config } from "./config.mjs";
import { closeDb } from "./db/client.mjs";
import { initializeRepositories } from "./repositories/index.mjs";
import { createQueueWorker } from "./worker/queueWorker.mjs";

const queueWorker = createQueueWorker();

if (config.storeMode === "memory") {
  console.error("Standalone queue worker requires TIKPAN_STORE=postgres so API and worker processes share tasks.");
  console.error("Use npm run dev for the single-process memory demo, or configure DATABASE_URL and PostgreSQL.");
  process.exit(1);
}

initializeRepositories()
  .then(() => {
    queueWorker.start();
    console.log(
      `Tikpan queue worker started as ${config.worker.id}; polling every ${config.worker.pollIntervalMs}ms.`
    );
  })
  .catch((error) => {
    console.error("Failed to initialize Tikpan queue worker.");
    console.error(error);
    process.exit(1);
  });

async function shutdown(signal) {
  console.log(`Received ${signal}; stopping Tikpan queue worker.`);
  queueWorker.stop();
  await closeDb();
  process.exit(0);
}

process.on("SIGTERM", () => {
  void shutdown("SIGTERM");
});

process.on("SIGINT", () => {
  void shutdown("SIGINT");
});

process.on("unhandledRejection", (error) => {
  console.error("Unhandled rejection in Tikpan queue worker.");
  console.error(error);
});
