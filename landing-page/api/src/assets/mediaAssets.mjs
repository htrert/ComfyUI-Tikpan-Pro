import { persistRemoteAsset } from "../storage/storageAdapters.mjs";

export async function registerTaskOutputAssets({ task, output, mediaRepository, createId }) {
  const publicUrls = normalizeArray(output?.publicUrls);
  const assetKeys = normalizeArray(output?.assets);
  const assets = [];
  const maxLength = Math.max(publicUrls.length, assetKeys.length);

  for (let index = 0; index < maxLength; index += 1) {
    const sourceUrl = publicUrls[index] ?? null;
    const mimeType = inferMimeType(sourceUrl ?? assetKeys[index]);
    const objectKey = toObjectKey(assetKeys[index], sourceUrl, task.id, index);
    const stored = await persistRemoteAsset({
      sourceUrl,
      objectKey,
      mimeType,
    });

    assets.push({
      id: createId("media"),
      taskId: task.id,
      userId: task.userId,
      direction: "output",
      objectKey: stored.objectKey,
      publicUrl: stored.publicUrl,
      mimeType: stored.mimeType,
      sizeBytes: stored.sizeBytes,
      width: null,
      height: null,
      durationSeconds: null,
      hash: stored.hash,
      sourceUrl: stored.sourceUrl,
      storageMode: stored.storageMode,
      createdAt: new Date().toISOString(),
    });
  }

  const savedAssets = await mediaRepository.createMany(assets);
  return {
    ...output,
    assets: savedAssets.map((asset) => asset.objectKey),
    publicUrls: savedAssets.map((asset) => asset.publicUrl).filter(Boolean),
    mediaAssets: savedAssets.map(publicMediaAsset),
  };
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function toObjectKey(assetKey, publicUrl, taskId, index) {
  if (typeof assetKey === "string" && assetKey.startsWith("r2://")) {
    return assetKey.replace(/^r2:\/\//, "");
  }

  if (typeof assetKey === "string" && assetKey.startsWith("remote://")) {
    return `remote/${taskId}/${index}`;
  }

  if (publicUrl) {
    return `remote/${taskId}/${index}`;
  }

  return `outputs/${taskId}-${index}.json`;
}

function inferMimeType(value) {
  const lower = String(value ?? "").toLowerCase();
  if (lower.endsWith(".png")) {
    return "image/png";
  }
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
    return "image/jpeg";
  }
  if (lower.endsWith(".webp")) {
    return "image/webp";
  }
  if (lower.endsWith(".mp4")) {
    return "video/mp4";
  }
  return "application/octet-stream";
}

function publicMediaAsset(asset) {
  return {
    id: asset.id,
    object_key: asset.objectKey,
    public_url: asset.publicUrl,
    mime_type: asset.mimeType,
    source_url: asset.sourceUrl,
    storage_mode: asset.storageMode,
    direction: asset.direction,
    created_at: asset.createdAt,
  };
}
