import { persistRemoteAsset } from "../src/storage/storageAdapters.mjs";
import { config } from "../src/config.mjs";

if (config.storageAdapterMode !== "local") {
  console.log(`Skipped local storage adapter contract in ${config.storageAdapterMode} mode.`);
  process.exit(0);
}

const stored = await persistRemoteAsset({
  sourceUrl: "https://example.com/demo.png",
  objectKey: "smoke/demo.png",
  mimeType: "image/png",
});

assertEqual(stored.storageMode, "local", "default storage adapter should be local");
assertEqual(stored.objectKey, "smoke/demo.png", "object key should be preserved");
assertEqual(stored.publicUrl, "https://cdn.example.com/smoke/demo.png", "public URL should use CDN base");
assertEqual(stored.sourceUrl, "https://example.com/demo.png", "source URL should be retained");

console.log("Checked storage adapter contract.");

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}. Expected ${expected}, received ${actual}.`);
  }
}
