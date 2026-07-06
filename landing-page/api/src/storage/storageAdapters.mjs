import { config } from "../config.mjs";
import { createHash } from "node:crypto";
import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

export async function persistRemoteAsset({ sourceUrl, objectKey, mimeType }) {
  const adapter = selectStorageAdapter();
  return adapter.persistRemoteAsset({ sourceUrl, objectKey, mimeType });
}

export function getStorageStatus() {
  const configured = isObjectStorageConfigured();
  const ready = config.storageAdapterMode === "local" || configured;

  return {
    mode: config.storageAdapterMode,
    ready,
    public_base_url: config.publicAssetBaseUrl,
    object_storage_configured: configured,
    max_remote_asset_bytes: config.remoteAssetMaxBytes,
  };
}

function selectStorageAdapter() {
  if (config.storageAdapterMode === "s3") {
    return s3StorageAdapter;
  }
  return localStorageAdapter;
}

const localStorageAdapter = {
  async persistRemoteAsset({ sourceUrl, objectKey, mimeType }) {
    return {
      objectKey,
      publicUrl: buildPublicUrl(objectKey),
      mimeType,
      sizeBytes: null,
      hash: null,
      sourceUrl,
      storageMode: "local",
    };
  },
};

const s3StorageAdapter = {
  async persistRemoteAsset({ sourceUrl, objectKey, mimeType }) {
    if (!isObjectStorageConfigured()) {
      throw new Error("S3/R2 storage adapter requires OBJECT_STORAGE_ENDPOINT, OBJECT_STORAGE_BUCKET, and credentials.");
    }

    if (!sourceUrl) {
      return {
        objectKey,
        publicUrl: buildPublicUrl(objectKey),
        mimeType,
        sizeBytes: null,
        hash: null,
        sourceUrl: null,
        storageMode: "s3",
      };
    }

    const remoteAsset = await fetchRemoteAsset(sourceUrl);
    const resolvedMimeType = remoteAsset.mimeType ?? mimeType ?? "application/octet-stream";

    await getS3Client().send(
      new PutObjectCommand({
        Bucket: config.objectStorage.bucket,
        Key: objectKey,
        Body: remoteAsset.body,
        ContentLength: remoteAsset.sizeBytes,
        ContentType: resolvedMimeType,
        Metadata: {
          source: "tikpan-task-output",
          sha256: remoteAsset.hash,
        },
      })
    );

    return {
      objectKey,
      publicUrl: buildPublicUrl(objectKey),
      mimeType: resolvedMimeType,
      sizeBytes: remoteAsset.sizeBytes,
      hash: remoteAsset.hash,
      sourceUrl,
      storageMode: "s3",
    };
  },
};

let s3Client = null;

function getS3Client() {
  if (!s3Client) {
    s3Client = new S3Client({
      region: config.objectStorage.region,
      endpoint: config.objectStorage.endpoint,
      forcePathStyle: config.objectStorage.forcePathStyle,
      credentials: {
        accessKeyId: config.objectStorage.accessKeyId,
        secretAccessKey: config.objectStorage.secretAccessKey,
      },
    });
  }

  return s3Client;
}

async function fetchRemoteAsset(sourceUrl) {
  const url = await validateRemoteAssetUrl(sourceUrl);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetchWithValidatedRedirects(url, {
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Remote asset download failed with HTTP ${response.status}.`);
    }

    const contentLength = Number(response.headers.get("content-length") ?? 0);
    if (contentLength > config.remoteAssetMaxBytes) {
      throw new Error("Remote asset exceeds configured size limit.");
    }

    const contentType = response.headers.get("content-type")?.split(";")[0]?.trim() || null;
    const chunks = [];
    let sizeBytes = 0;

    for await (const chunk of response.body) {
      sizeBytes += chunk.byteLength;
      if (sizeBytes > config.remoteAssetMaxBytes) {
        throw new Error("Remote asset exceeds configured size limit.");
      }
      chunks.push(Buffer.from(chunk));
    }

    const body = Buffer.concat(chunks);
    return {
      body,
      sizeBytes,
      mimeType: contentType,
      hash: createHash("sha256").update(body).digest("hex"),
    };
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Remote asset download timed out.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchWithValidatedRedirects(initialUrl, { signal }) {
  let currentUrl = initialUrl;

  for (let redirectCount = 0; redirectCount <= 5; redirectCount += 1) {
    const response = await fetch(currentUrl, {
      method: "GET",
      redirect: "manual",
      signal,
    });

    if (![301, 302, 303, 307, 308].includes(response.status)) {
      return response;
    }

    const location = response.headers.get("location");
    if (!location) {
      throw new Error("Remote asset redirect did not include a target location.");
    }

    currentUrl = await validateRemoteAssetUrl(new URL(location, currentUrl).toString());
  }

  throw new Error("Remote asset exceeded maximum redirect count.");
}

async function validateRemoteAssetUrl(sourceUrl) {
  if (!sourceUrl) {
    throw new Error("S3/R2 storage adapter requires a remote source URL.");
  }

  let url;
  try {
    url = new URL(sourceUrl);
  } catch {
    throw new Error("Remote asset URL is invalid.");
  }

  if (!["https:", "http:"].includes(url.protocol)) {
    throw new Error("Remote asset URL must use HTTP or HTTPS.");
  }

  if (isPrivateHost(url.hostname)) {
    throw new Error("Remote asset URL points to a private host.");
  }

  await assertPublicDnsTarget(url.hostname);
  return url;
}

async function assertPublicDnsTarget(hostname) {
  if (isIP(hostname)) {
    return;
  }

  const records = await lookup(hostname, { all: true, verbatim: true });
  if (records.some((record) => isPrivateHost(record.address))) {
    throw new Error("Remote asset URL resolves to a private host.");
  }
}

function isPrivateHost(hostname) {
  const normalized = hostname.toLowerCase();
  if (
    normalized === "localhost" ||
    normalized.endsWith(".localhost") ||
    normalized === "0.0.0.0" ||
    normalized === "127.0.0.1" ||
    normalized === "::1" ||
    normalized.startsWith("fc") ||
    normalized.startsWith("fd") ||
    normalized.startsWith("fe80:")
  ) {
    return true;
  }

  if (normalized.startsWith("::ffff:")) {
    return isPrivateHost(normalized.slice("::ffff:".length));
  }

  const ipv4 = normalized.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (!ipv4) {
    return false;
  }

  const first = Number(ipv4[1]);
  const second = Number(ipv4[2]);

  return (
    first === 10 ||
    first === 127 ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168) ||
    (first === 169 && second === 254)
  );
}

function buildPublicUrl(objectKey) {
  const base = config.publicAssetBaseUrl.replace(/\/+$/, "");
  const path = String(objectKey).replace(/^\/+/, "");
  return `${base}/${path}`;
}

function isObjectStorageConfigured() {
  return Boolean(
    config.objectStorage.endpoint &&
      config.objectStorage.bucket &&
      config.objectStorage.accessKeyId &&
      config.objectStorage.secretAccessKey
  );
}
