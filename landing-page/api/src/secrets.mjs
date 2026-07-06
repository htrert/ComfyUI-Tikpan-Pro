import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { config } from "./config.mjs";

const encryptedPrefix = "enc:v1:";

export function encryptSecret(value) {
  const text = String(value ?? "").trim();
  if (!text || text.startsWith(encryptedPrefix) || text.startsWith("demo-encrypted-")) {
    return text || null;
  }

  if (!config.secretsEncryptionKey) {
    return text;
  }

  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const ciphertext = Buffer.concat([cipher.update(text, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `${encryptedPrefix}${Buffer.concat([iv, tag, ciphertext]).toString("base64url")}`;
}

export function decryptSecret(value) {
  const text = String(value ?? "").trim();
  if (!text || !text.startsWith(encryptedPrefix)) {
    return text || null;
  }

  if (!config.secretsEncryptionKey) {
    const error = new Error("TIKPAN_SECRETS_ENCRYPTION_KEY is required to decrypt stored provider secrets.");
    error.code = "SECRET_DECRYPTION_KEY_MISSING";
    throw error;
  }

  const payload = Buffer.from(text.slice(encryptedPrefix.length), "base64url");
  if (payload.length <= 28) {
    const error = new Error("Encrypted provider secret payload is invalid.");
    error.code = "SECRET_DECRYPTION_FAILED";
    throw error;
  }

  const iv = payload.subarray(0, 12);
  const tag = payload.subarray(12, 28);
  const ciphertext = payload.subarray(28);
  const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
}

export function redactSecret(value) {
  const text = decryptableLabel(value);
  if (!text) {
    return null;
  }
  if (text.startsWith(encryptedPrefix)) {
    return "enc:v1:****";
  }
  if (text.length <= 8) {
    return "****";
  }
  return `${text.slice(0, 4)}****${text.slice(-4)}`;
}

function decryptableLabel(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  if (text.startsWith(encryptedPrefix)) {
    return text;
  }
  return text;
}

function encryptionKey() {
  return createHash("sha256").update(config.secretsEncryptionKey).digest();
}
