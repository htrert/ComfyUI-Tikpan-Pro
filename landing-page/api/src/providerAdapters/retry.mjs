const retryableCodes = new Set(["PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMITED", "PROVIDER_NETWORK_ERROR", "PROVIDER_5XX"]);

export async function retryWithBackoff(operation, options = {}) {
  const retries = Number(options.retries ?? 1);
  const baseDelayMs = Number(options.baseDelayMs ?? 120);
  let lastError = null;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await operation({ attempt });
    } catch (error) {
      lastError = error;
      if (attempt >= retries || !isRetryableProviderError(error)) {
        throw error;
      }
      await delay(baseDelayMs * 2 ** attempt);
    }
  }

  throw lastError;
}

export function isRetryableProviderError(error) {
  return retryableCodes.has(error?.code);
}

export function providerError(code, message, extra = {}) {
  const error = new Error(message);
  error.code = code;
  error.extra = extra;
  return error;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
